class XUIException(Exception):
    """Base exception for 3x-ui integration."""
    pass


class XUIAuthException(XUIException):
    """Raised when authentication fails."""
    pass


class XUIConnectionException(XUIException):
    """Raised when connection to 3x-ui fails."""
    pass


class XUIClientNotFoundException(XUIException):
    """Raised when a client is not found in 3x-ui."""
    pass


class XUIServerException(XUIException):
    """Raised when 3x-ui returns a server-side error."""
    pass


class XUITimeoutException(XUIException):
    """Raised when a request to 3x-ui times out."""
    pass
