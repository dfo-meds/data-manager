"""Provides a wrapper class around the SQLAlchemy engine that makes it easier to use."""
import functools

import sqlalchemy as sa
import sqlalchemy.orm as orm
import zirconium as zr
from autoinject import injector
import zrlog
import gc

from sqlalchemy.exc import DisconnectionError, TimeoutError

from .orm import Base
import typing as t

from ..util.errors import RecoverableError


def wrap_orm_errors(cb: t.Callable) -> t.Callable:

    @functools.wraps(cb)
    def _inner(*args, **kwargs):
        try:
            return cb(*args, **kwargs)
        except (TimeoutError, DisconnectionError) as e:
            raise RecoverableError(str(e)) from e
    return _inner

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
            x = getattr(self._transaction, item)
        else:
            x = getattr(self._session, item)
        if callable(x):
            return wrap_orm_errors(x)
        else:
            return x

    @wrap_orm_errors
    def commit(self):
        """Override commit() by passing it to the Database to handle."""
        self._transaction = self.db.commit_last_tx()

    @wrap_orm_errors
    def rollback(self):
        """Override rollback() by passing it to the Database to handle."""
        self._transaction = self.db.rollback_last_txt()

    @wrap_orm_errors
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
        self._session = None
        self._transaction_stack: list[orm.SessionTransaction] = []
        self._is_closed = False
        self.engine = None
        self._log = zrlog.get_logger("pipeman.db")
        self._maker = None

    def get_maker(self) -> orm.sessionmaker:
        if self._maker is None:
            self._maker = orm.sessionmaker(bind=self.get_engine())
        return self._maker

    def get_engine(self):
        if self.engine is None:
            self._log.debug(f"Opening database connection pool")
            self.engine = sa.engine_from_config(self.config["database"], prefix="")
        return self.engine

    @wrap_orm_errors
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
            self._session = self.get_maker()()
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
                if self._transaction_stack[-1].is_active:
                    self._transaction_stack[-1].rollback()
            else:
                self._log.debug("Automatic commit")
                if self._transaction_stack[-1].is_active:
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

    def close(self):
        self._close()

    def __cleanup__(self):
        self._close()
        self._is_closed = True

    def _close(self):
        while self._transaction_stack:
            self._log.debug("Autorolling back transaction")
            if self._transaction_stack[-1].is_active:
                self._transaction_stack[-1].rollback()
            del self._transaction_stack[-1]
        if self._session:
            self._log.debug("Closing database session")
            self._session.close()
            self._session = None
        if self._maker:
            self._maker.close_all()
            self._maker= None
        if self.engine is not None:
            self._log.debug("Closing database connection pool")
            self.engine.dispose()
            self.engine = None

    @wrap_orm_errors
    def commit_last_tx(self) -> orm.SessionTransaction:
        """Commit the most recent transaction, close it, and start a new one."""
        if self._transaction_stack:
            if self._transaction_stack[-1].is_active:
                self._transaction_stack[-1].commit()
            del self._transaction_stack[-1]
            if self._transaction_stack:
                self._transaction_stack.append(self._session.begin_nested())
            else:
                self._transaction_stack.append(self._session.begin())
            return self._transaction_stack[-1]

    @wrap_orm_errors
    def rollback_last_tx(self) -> orm.SessionTransaction:
        """Rollback the most recent transaction, close it, and start a new one."""
        if self._transaction_stack:
            if self._transaction_stack[-1].is_active:
                self._transaction_stack[-1].rollback()
            del self._transaction_stack[-1]
            if self._transaction_stack:
                self._transaction_stack.append(self._session.begin_nested())
            else:
                self._transaction_stack.append(self._session.begin())
            return self._transaction_stack[-1]

    @wrap_orm_errors
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
