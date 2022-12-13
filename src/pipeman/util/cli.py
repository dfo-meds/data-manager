from .errors import UserInputError


def no_error_wrapper(no_error, callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex
