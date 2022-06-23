r"""Base code for :class:`~.Type`\s."""

import abc
import inspect
import copy
import functools

from .. import util
from ..dyn_value import DynamicValue

__all__ = [
    "TypeContext",
    "NoStaticSizeError",
    "Type",
]

class TypeContext:
    """The context for a :class:`Type`.

    Parameters
    ----------
    packet : :class:`~.Packet`
        The packet instance that's being marshaled.
    ctx : :class:`~.PacketContext`
        The context for the packet that's being marshaled.

        Getting attributes that are not directly in the
        :class:`TypeContext` will be gotten from the
        packet context.

    Attributes
    ----------
    packet : :class:`~.Packet` or ``None``
        The packet instance that's being marshaled.
    packet_ctx : :class:`~.PacketContext` or ``None``
        The context for the packet that's being marshaled.

        Getting attributes that are not directly in the
        :class:`~TypeContext` will be gotten from this.
    """

    def __init__(self, packet=None, *, ctx=None):
        self.packet     = packet
        self.packet_ctx = ctx

    def __getattr__(self, attr):
        if self.packet_ctx is None:
            raise AttributeError(f"'{type(self).__qualname__}' object has no attribute '{attr}'")

        return getattr(self.packet_ctx, attr)

    # Disable hashing since 'Packet' is unhashable.
    __hash__ = None

class NoStaticSizeError(Exception):
    """An error indicating a :class:`Type` has no static size.

    Parameters
    ----------
    type_cls : subclass of :class:`Type`
        The :class:`Type` which has no static size.
    """

    def __init__(self, type_cls):
        super().__init__(f"'{type_cls.__qualname__}' has no static size")

class Type(abc.ABC):
    r"""A definition of how to marshal raw data to and from values.

    Typically used for the types of :class:`~.Packet` fields.

    When :class:`Types <Type>` are called, their :meth:`_call`
    :class:`classmethod` gets called, returning a new :class:`Type`.

    :class:`~.Array` types can be constructed using indexing syntax,
    like so::

        >>> import pak
        >>> array = pak.Int8[3]
        >>> array
        <class 'pak.types.array.Int8[3]'>
        >>> array.pack([1, 2, 3])
        b'\x01\x02\x03'
        >>> array.unpack(b"\x01\x02\x03")
        [1, 2, 3]

    The object within the brackets gets passed as the ``size`` parameter
    to :class:`~.Array`.

    Parameters
    ----------
    typelike
        The typelike object to convert to a :class:`Type`.

    Raises
    ------
    :exc:`TypeError`
        If ``typelike`` can't be converted to a :class:`Type`.
    """

    _typelikes = {}

    _size    = None
    _default = None

    def __new__(cls, typelike):
        if isinstance(typelike, type) and issubclass(typelike, Type):
            return typelike

        for typelike_cls, converter in cls._typelikes.items():
            if isinstance(typelike, typelike_cls):
                return converter(typelike)

        raise TypeError(f"Object {typelike} is not typelike")

    @classmethod
    def register_typelike(cls, typelike_cls, converter):
        """Registers a class as being convertible to a :class:`Type`.

        Parameters
        ----------
        typelike_cls : :class:`type`
            The convertible type.
        converter : callable
            The object called to convert the object to a :class:`Type`.
        """

        cls._typelikes[typelike_cls] = converter

    @classmethod
    def unregister_typelike(cls, typelike_cls):
        """Unregisters a class as being convertible to a :class:`Type`.

        Parameters
        ----------
        typelike_cls : :class:`type`
            The type to unregister.
        """

        cls._typelikes.pop(typelike_cls)

    @classmethod
    def is_typelike(cls, obj):
        """Gets whether an object is typelike.

        Parameters
        ----------
        obj
            The object to check.

        Returns
        -------
        :class:`bool`
            Whether ``obj`` is typelike.
        """

        if isinstance(obj, type) and issubclass(obj, Type):
            return True

        for typelike_cls in cls._typelikes.keys():
            if isinstance(obj, typelike_cls):
                return True

        return False

    @staticmethod
    def prepare_types(func):
        """A decorator that converts arguments annotated with :class:`Type` to a :class:`Type`."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            args_annotations, kwargs_annotations = util.bind_annotations(func, *args, **kwargs)

            new_args = [
                Type(value) if annotation is Type
                else value

                for value, annotation in args_annotations
            ]

            new_kwargs = {
                name: (
                    Type(value) if annotation is Type
                    else value
                )

                for name, (value, annotation) in kwargs_annotations.items()
            }

            return func(*new_args, **new_kwargs)

        return wrapper

    @classmethod
    def __class_getitem__(cls, index):
        """Gets an :class:`.Array` of the :class:`Type`.

        Parameters
        ----------
        index : :class:`int` or subclass of :class:`Type` or :class:`str` or :class:`function` or ``None``
            The ``size`` argument passed to :class:`~.Array`.

        Examples
        --------
        >>> import pak
        >>> pak.Int8[3]
        <class 'pak.types.array.Int8[3]'>
        """

        from .array import Array

        return Array(cls, index)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls._size    = DynamicValue(inspect.getattr_static(cls, "_size"))
        cls._default = DynamicValue(inspect.getattr_static(cls, "_default"))

        # Set __new__ to _call's underlying function.
        # We don't just override __new__ instead of
        # _call so that it's more clear that calling
        # a Type is separate from actually initializing
        # an instance of Type.
        #
        # We don't use a metaclass to override construction
        # outright to simplify code. There is a possibility
        # that if the '_call' method returns an instance of
        # the type being called, it will go through to '__init__',
        # but that will raise an error in '__init__' and
        # shouldn't happen anyways.
        cls.__new__ = cls._call.__func__

    def __init__(self):
        raise TypeError("Types do not get initialized normally.")

    @classmethod
    def descriptor(cls):
        """Gets the descriptor form of the :class:`Type`.

        Returns
        -------
        :class:`Type`
            The descriptor form of the :class:`Type`.
        """

        return object.__new__(cls)

    def __set_name__(self, owner, name):
        self.attr_name = f"_{name}_type_value"

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        return getattr(instance, self.attr_name)

    def __set__(self, instance, value):
        setattr(instance, self.attr_name, value)

    def __delete__(self, instance):
        delattr(instance, self.attr_name)

    STATIC_SIZE = util.UniqueSentinel("STATIC_SIZE")

    @classmethod
    def size(cls, value=STATIC_SIZE, *, ctx=None):
        r"""Gets the size of the :class:`Type` when packed.

        Worst case this will perform as badly as packing the value
        and getting the length of the raw data performs. However,
        :class:`Type`\s may often be able to optimize finding their
        packed sizes.

        If the :attr:`_size` attribute is any value other than ``None``,
        then that value will be returned.

        Else, If the :attr:`_size` attribute is a :class:`classmethod`,
        then it should look like this::

            @classmethod
            def _size(cls, value, *, ctx):
                return my_size

        The return value of the :class:`classmethod` will be returned from
        this method.

        Otherwise, if the :attr:`_size` attribute is a :class:`DynamicValue`,
        which it is automatically transformed into on class construction
        if applicable, then the dynamic value of that is returned.

        If any of these give a size of ``None`` or raise :exc:`NoStaticSizeError`,
        then if ``value`` is not :attr:`STATIC_SIZE`, then the value will be
        packed in order to get the size.

        Parameters
        ----------
        value : any
            If :attr:`STATIC_SIZE`, then a size irrespective of
            any value is returned, if possible.

            Otherwise,
        ctx : :class:`TypeContext` or ``None``
            The context for the :class:`Type`

            If ``None``, then an empty :class:`TypeContext` is used.

        Returns
        -------
        :class:`int`
            The size of the :class:`Type` when packed.

        Raises
        ------
        :exc:`NoStaticSizeError`
            If the :class:`Type` has no static size but is asked for one.
        """

        if ctx is None:
            ctx = TypeContext()

        size = cls._size

        try:
            if inspect.ismethod(size):
                size = size(value, ctx=ctx)
            elif isinstance(size, DynamicValue):
                size = size.get(ctx=ctx)

        except NoStaticSizeError:
            size = None

        # If no (hopefully) performant calculation of a value's
        # packed size is available, then fallback to packing the value.
        if size is None:
            if value is cls.STATIC_SIZE:
                raise NoStaticSizeError(cls)

            size = len(cls.pack(value, ctx=ctx))

        return size

    @classmethod
    def default(cls, *, ctx=None):
        """Gets the default value of the :class:`Type`.

        If the :attr:`_default` attribute is a :class:`classmethod`,
        then it should look like this::

            @classmethod
            def _default(cls, *, ctx):
                return my_default_value

        The return value of the :class:`classmethod` will be returned from
        this method.

        Else, if the :attr:`_default` attribute is a :class:`DynamicValue`,
        which it is automatically transformed into on class construction
        if applicable, then the dynamic value of that is returned.

        Otherwise, if the :attr:`_default` attribute is any value
        other than ``None``, a deepcopy of that value will be returned.

        Parameters
        ----------
        ctx : :class:`TypeContext` or ``None``
            The context for the type.

            If ``None``, then an empty :class:`TypeContext` is used.

        Returns
        -------
        any
            The default value.

        Raises
        ------
        :exc:`TypeError`
            If the :class:`Type` has no default value..
        """

        if cls._default is None:
            raise TypeError(f"'{cls.__qualname__}' has no default value")

        if ctx is None:
            ctx = TypeContext()

        if inspect.ismethod(cls._default):
            return cls._default(ctx=ctx)

        if isinstance(cls._default, DynamicValue):
            return cls._default.get(ctx=ctx)

        # Deepcopy because the default could be mutable.
        return copy.deepcopy(cls._default)

    @classmethod
    def unpack(cls, buf, *, ctx=None):
        """Unpacks raw data into its corresponding value.

        Warnings
        --------
        Do **not** override this method. Instead override
        :meth:`_unpack`.

        Parameters
        ----------
        buf : file object or :class:`bytes` or :class:`bytearray`
            The buffer containing the raw data.
        ctx : :class:`TypeContext` or ``None``
            The context for the type.

            If ``None``, then an empty :class:`TypeContext` is used.

        Returns
        -------
        any
            The corresponding value of the buffer.
        """

        buf = util.file_object(buf)

        if ctx is None:
            ctx = TypeContext()

        return cls._unpack(buf, ctx=ctx)

    @classmethod
    def pack(cls, value, *, ctx=None):
        """Packs a value into its corresponding raw data.

        Warnings
        --------
        Do **not** override this method. Instead override
        :meth:`_pack`.

        Parameters
        ----------
        value
            The value to pack.
        ctx : :class:`TypeContext` or ``None``
            The context for the type.

            If ``None``, then an empty :class:`TypeContext` is used.

        Returns
        -------
        :class:`bytes`
            The corresponding raw data.
        """

        if ctx is None:
            ctx = TypeContext()

        return cls._pack(value, ctx=ctx)

    @classmethod
    @abc.abstractmethod
    def _unpack(cls, buf, *, ctx):
        """Unpacks raw data into its corresponding value.

        To be overridden by subclasses.

        Warnings
        --------
        Do not use this method directly, **always** use
        :meth:`unpack` instead.

        Parameters
        ----------
        buf : file object
            The buffer containing the raw data.
        ctx : :class:`TypeContext`
            The context for the type.

        Returns
        -------
        any
            The corresponding value from the buffer.
        """

        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def _pack(cls, value, *, ctx):
        """Packs a value into its corresponding raw data.

        To be overridden by subclasses.

        Warnings
        --------
        Do not use this method directly, **always** use
        :meth:`pack` instead.

        Parameters
        ----------
        value
            The value to pack.
        ctx : :class:`TypeContext`
            The context for the type.

        Returns
        -------
        :class:`bytes`
            The corresponding raw data.
        """

        raise NotImplementedError

    @classmethod
    @util.cache(force_hashable=False)
    def make_type(cls, name, bases=None, **namespace):
        """Utility for generating new types.

        The generated type's :attr:`__module__` attribute is
        set to be the same as the origin type's. This is done to
        get around an issue where generated types would have
        their :attr:`__module__` attribute be ``"abc"`` because
        :class:`Type` inherits from :class:`abc.ABC`.

        This method is cached so a new type is only made if it
        hasn't been made before.

        Parameters
        ----------
        name : :class:`str`
            The generated type's name.
        bases : :class:`tuple`
            The generated type's base classes. If unspecified, the
            origin type is the sole base class.
        **namespace
            The attributes and corresponding values of the generated
            type.

        Returns
        -------
        subclass of :class:`Type`
            The generated type.
        """

        if bases is None:
            bases = (cls,)

        namespace.setdefault("__module__", cls.__module__)

        return type(name, bases, namespace)

    @classmethod
    def _call(cls):
        # Called when the type's constructor is called.
        #
        # The arguments passed to the constructor get forwarded
        # to this method. typically overridden to enable
        # generating new types.

        raise NotImplementedError
