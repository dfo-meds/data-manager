"""Provides a wrapper class around the SQLAlchemy engine that makes it easier to use."""
import sqlalchemy as sa
import sqlalchemy.orm as orm
import zirconium as zr
from autoinject import injector
import logging
import traceback

from .orm import Base


class SessionWrapper:
    """Wrapper for a session to allow users to call methods on either the transaction or session object.
    Parameters
    ----------
    db: metadb.db.Database
        The Database object.
    session: orm.Session
        The session object.
    transaction: orm.SessionTransaction
        The transaction object.
    """

    def __init__(self, db, session: orm.Session, transaction: orm.SessionTransaction):
        """Implement __init__()."""
        self.db = db
        self._session = session
        self._transaction = transaction

    def __getattr__(self, item):
        """Implement. __getattr___() by delegating to the transaction if possible, and then the session."""
        if hasattr(self._transaction, item):
            return getattr(self._transaction, item)
        else:
            return getattr(self._session, item)

    def commit(self):
        """Override commit() by passing it to the Database to handle."""
        self._transaction = self.db.commit_last_tx()

    def rollback(self):
        """Override rollback() by passing it to the Database to handle."""
        self._transaction = self.db.rollback_last_txt()

    def execute(self, statement, *args, **kwargs):
        """Pass execute() directly to the session."""
        return self._session.execute(statement, *args, **kwargs)


@injector.injectable
class Database:
    """Represents the database that the application is connected to.
    Uses the Injectable pattern to ensure we only get a single instance of it. The connection string should be
    stored in a configuration file (see Zirconium documentation) using the following template:
    [database]
    connection_string: CONNECTION_STRING
    """

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        """Implement __init__()."""
        self.engine = None
        self._session = None
        self._transaction_stack = []
        self._is_closed = False
        self.log = logging.getLogger("pipeman.db")
        self.log_safe = logging.getLogger("pipeman.db.safe")
        self.log_safe.omit_extras()
        self.log_safe.info(f"Initializing DB in: {injector.context_manager._get_context_hash()}")
        self._unclean_warned_once = False
        self._closing_warned_once = False

    def _create_connection(self):
        if self.engine is None:
            if self._is_closed and not self._unclean_warned_once:
                self.log_safe.info(f"Recreating connection DB out of context {injector.context_manager._get_context_hash()}")
                self.log_safe.warning(f"Reconnecting SQLAlchemy engine on a closed object {hash(self)}")
                self._unclean_warned_once = True
            # Create the engine from the connection string
            self.engine = sa.engine_from_config(self.config["database"], prefix="")

    def __enter__(self) -> SessionWrapper:
        """Implement __enter__().
        Create a new session if none exists, then starts a new transaction (even
        if one exists). This nesting of transactions enables commit() and rollback() to only affect statements
        executed within the context manager block.
        Returns
        -------
        SessionWrapper
            An instance of SessionWrapper that wraps both the session and transaction object.
        """
        self._create_connection()
        if self._session is None:
            self._session = orm.Session(self.engine)
            self._transaction_stack = [self._session.begin()]
        else:
            self._transaction_stack.append(self._session.begin_nested())
        return SessionWrapper(self, self._session, self._transaction_stack[-1])

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Implement __exit__().
        Parameters
        ----------
        exc_type
            Exception type
        exc_val
            Exception value
        exc_tb
            Exception traceback
        If there is an error, the transaction is rolled back, otherwise it is committed. The
        session is closed once the transaction stack is empty.
        """
        r = False
        if self._transaction_stack:
            if exc_type:
                self._transaction_stack[-1].rollback()
            else:
                self._transaction_stack[-1].commit()
            del self._transaction_stack[-1]
        else:
            if not self._closing_warned_once:
                r = True
                self.log_safe.exception("Transaction stack empty when it shouldn't be!")
        if not self._transaction_stack:
            if self._session:
                self._session.close()
                self._session = None
            else:
                if not self._closing_warned_once:
                    r = True
                    self.log_safe.exception("Session empty when it shouldn't be!")
            if self._is_closed:
                if not self._closing_warned_once:
                    r = True
                    self.log_safe.warning("Closing engine because this should be closed and might not be properly closed later")
                self.close()
        if r:
            self._closing_warned_once = True

    def __cleanup__(self):
        self.close()
        self._is_closed = True

    def close(self):
        while self._transaction_stack:
            self._transaction_stack[-1].rollback()
            del self._transaction_stack[-1]
        if self._session:
            self._session.close()
            self._session = None
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None

    def commit_last_tx(self) -> orm.SessionTransaction:
        """Commit the most recent transaction, close it, and start a new one."""
        if self._transaction_stack:
            self._transaction_stack[-1].commit()
            del self._transaction_stack[-1]
            if self._transaction_stack:
                self._transaction_stack.append(self._session.begin_nested())
            else:
                self._transaction_stack.append(self._session.begin())
            return self._transaction_stack[-1]

    def rollback_last_tx(self) -> orm.SessionTransaction:
        """Rollback the most recent transaction, close it, and start a new one."""
        if self._transaction_stack:
            self._transaction_stack[-1].rollback()
            del self._transaction_stack[-1]
            if self._transaction_stack:
                self._transaction_stack.append(self._session.begin_nested())
            else:
                self._transaction_stack.append(self._session.begin())
            return self._transaction_stack[-1]

    def create_database(self, recreate: bool = False):
        """Create the database.
        Parameters
        ----------
        recreate: bool
            If true, the database is first dropped.
        """
        if recreate:
            Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
