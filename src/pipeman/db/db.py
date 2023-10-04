"""Provides a wrapper class around the SQLAlchemy engine that makes it easier to use."""
import sqlalchemy as sa
import sqlalchemy.orm as orm
import zirconium as zr
from autoinject import injector
import zrlog
import gc

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


@injector.injectable_global
class DatabasePool:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.engine = None
        self._log = zrlog.get_logger("pipeman.db_pool")

    def get_engine(self):
        if self.engine is None:
            self._log.debug(f"Opening database connection pool")
            self.engine = sa.engine_from_config(self.config["database"], prefix="")
        return self.engine

    def __cleanup__(self):
        self.close()

    def close(self):
        if self.engine is not None:
            self._log.debug("Closing database connection pool")
            self.engine.dispose()
            del self.engine
            self.engine = None
            gc.collect()


@injector.injectable
class Database:
    """Represents the database that the application is connected to.
    Uses the Injectable pattern to ensure we only get a single instance of it. The connection string should be
    stored in a configuration file (see Zirconium documentation) using the following template:
    [database]
    connection_string: CONNECTION_STRING
    """

    db_pool: DatabasePool = None

    @injector.construct
    def __init__(self):
        """Implement __init__()."""
        self._session = None
        self._transaction_stack = []
        self._is_closed = False
        self._log = zrlog.get_logger("pipeman.db")

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
        if self._session is None:
            self._log.debug("Opening session")
            self._session = orm.Session(self.db_pool.get_engine())
            self._transaction_stack = [self._session.begin()]
        else:
            self._log.debug("Begining nested session")
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
        If there is an error, the transaction is rolled back, otherwise it is committed.
        """
        if self._transaction_stack:
            if exc_type:
                self._log.debug("Automatic rollback")
                self._transaction_stack[-1].rollback()
            else:
                self._log.debug("Automatic commit")
                self._transaction_stack[-1].commit()
            del self._transaction_stack[-1]
        else:
            self._log.info(f"Database transaction stack empty during __exit__")
        if not self._transaction_stack:
            if self._session:
                self._log.debug("Closing session")
                self._session.close()
                self._session = None
            else:
                self._log.info(f"Database session not set")
        if self._is_closed and not self._transaction_stack:
            self._log.info(f"Database object used after cleanup called")
            self._close()

    def __cleanup__(self):
        self._close()
        self._is_closed = True

    def _close(self):
        while self._transaction_stack:
            self._log.debug("Autorolling back transaction")
            self._transaction_stack[-1].rollback()
            del self._transaction_stack[-1]
        if self._session:
            self._log.debug("Closing database session")
            self._session.close()
            self._session = None

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
            self._log.warning(f"Dropping all tables")
            Base.metadata.drop_all(self.engine)
        self._log.notice("Creating all tables")
        Base.metadata.create_all(self.engine)
