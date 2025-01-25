import logging
from functools import wraps
import traceback

def with_error_handling(logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}")
                logger.debug(traceback.format_exc())
                return None
        return wrapper
    return decorator 