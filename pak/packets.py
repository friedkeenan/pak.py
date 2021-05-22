"""Generic code for packets."""

# This module isn't split up currently because it has
# so few members, but in the event it gets too large,
# it should be split up.

from . import util
from .types import Type, TypeContext, RawByte

__all__ = [
    "PacketContext",
    "Packet",
    "GenericPacket",
]

class PacketContext:
    """The context for a :class:`Packet`.

    To be inherited from by users of the library
    for their own contexts.
    """

class Packet:
    r"""A collection of values that can be marshaled to and from
    raw data using :class:`Types <.Type>`.

    The difference between a :class:`Packet` and a :class:`~.Type`
    is that :class:`Types <.Type>` only define how to marshal
    values to and from raw data, while :class:`Packets <Packet>`
    actually *contain* values themselves.

    To unpack a :class:`Packet` from raw data, you should use
    the :meth:`unpack` method instead of the constructor.

    Parameters
    ----------
    ctx : :class:`PacketContext`
        The context for the :class:`Packet`.
    **kwargs
        The attributes and corresponding values of the
        :class:`Packet`.

    Raises
    ------
    :exc:`TypeError`
        If there are any superfluous keyword arguments.

    Examples
    --------
    Basic functionality::

        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     attr1: pak.Int8
        ...     attr2: pak.Int16
        ...
        >>> p = MyPacket()
        >>> p
        MyPacket(attr1=0, attr2=0)
        >>> p.pack()
        b'\x00\x00\x00'
        >>> p = MyPacket(attr1=1, attr2=2)
        >>> p.pack()
        b'\x01\x02\x00'
        >>> MyPacket.unpack(b"\xff\x00\x80")
        MyPacket(attr1=-1, attr2=-32768)

    Additonally your attributes can be properties::

        >>> class MyPacket(pak.Packet):
        ...     prop: pak.Int8
        ...     @property
        ...     def prop(self):
        ...         return self._prop
        ...     @prop.setter
        ...     def prop(self, value):
        ...         self._prop = value + 1
        ...
        >>> p = MyPacket()
        >>> p # Int8's default is 0, plus 1 is 1
        MyPacket(prop=1)
        >>> p.prop = 2
        >>> p
        MyPacket(prop=3)
        >>> p.pack()
        b'\x03'

    If an attribute is read only, it will only raise an error
    if you explicitly try to set it, i.e. you specify the value
    for it in the constructor.
    """

    @classmethod
    def _init_fields_from_annotations(cls):
        cls._fields = {}

        # In 3.10+ we can use inspect.get_annotations()
        annotations = getattr(cls, "__annotations__", None)
        if annotations is None:
            return

        for attr, attr_type in annotations.items():
            real_type = Type(attr_type)

            cls._fields[attr] = real_type

            # Only add the Type descriptor
            # if there isn't already something
            # in its place (like a property).
            if not hasattr(cls, attr):
                descriptor = real_type.descriptor()

                # Set the name manually because __set_name__
                # only gets called on typee construction, and
                # furthermore before __init_subclass__ is called.
                descriptor.__set_name__(cls, attr)

                setattr(cls, attr, descriptor)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls._init_fields_from_annotations()

    def __init__(self, *, ctx=None, **kwargs):
        type_ctx = self.type_ctx(ctx)
        for attr, attr_type in self.enumerate_field_types():
            if attr in kwargs:
                setattr(self, attr, kwargs.pop(attr))
            else:
                default = attr_type.default(ctx=type_ctx)
                try:
                    setattr(self, attr, default)
                except AttributeError:
                    # If trying to set a default fails
                    # (like if the attribute is read-only)
                    # then just move on.
                    pass

        # All the kwargs should be used up by the end of the
        # above loop because we pop them out.
        if len(kwargs) > 0:
            raise TypeError(f"Unexpected keyword arguments for {type(self).__name__}: {kwargs}")

    @classmethod
    def unpack(cls, buf, *, ctx=None):
        """Unpacks a :class:`Packet` from raw data.

        Parameters
        ----------
        buf : file object or :class:`bytes` or :class:`bytearray`
            The buffer containing the raw data.
        ctx : :class:`PacketContext`
            The context for the :class:`Packet`.

        Returns
        -------
        :class:`Packet`
            The :class:`Packet` marshaled from the raw data.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     hello: pak.RawByte[5]
        ...     world: pak.RawByte[5]
        ...
        >>> MyPacket.unpack(b"HelloWorld")
        MyPacket(hello=bytearray(b'Hello'), world=bytearray(b'World'))
        """

        self = object.__new__(cls)

        buf = util.file_object(buf)

        type_ctx = self.type_ctx(ctx)
        for attr, attr_type in cls.enumerate_field_types():
            value = attr_type.unpack(buf, ctx=type_ctx)

            try:
                setattr(self, attr, value)
            except AttributeError:
                # If trying to set an unpacked value fails
                # (like if the attribute is read-only)
                # then just move on.
                pass

        return self

    def pack(self, *, ctx=None):
        r"""Packs a :class:`Packet` to raw data.

        Parameters
        ----------
        ctx : :class:`PacketContext`
            The context for the :class:`Packet`.

        Returns
        -------
        :class:`bytes`
            The raw data marshaled from the :class:`Packet`.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     array: pak.UInt8[pak.UInt8]
        ...
        >>> p = MyPacket(array=[0, 1, 2, 3])
        >>> p.pack()
        b'\x04\x00\x01\x02\x03'
        """

        type_ctx = self.type_ctx(ctx)

        return b"".join(
            attr_type.pack(value, ctx=type_ctx)
            for _, attr_type, value in self.enumerate_field_types_and_values()
        )

    def type_ctx(self, ctx):
        """Converts a :class:`PacketContext` to a :class:`~.TypeContext`.

        Parameters
        ----------
        ctx : :class:`PacketContext`
            The context for the :class:`Packet`.

        Returns
        -------
        :class:`~.TypeContext`
            The context for a :class:`~.Type`.
        """

        return TypeContext(self, ctx=ctx)

    @classmethod
    def enumerate_field_types(cls):
        """Enumerates the :class:`Types <.Type>` of the fields of the :class:`Packet`.

        Returns
        -------
        iterable
            Each element of the iterable is a (``attr_name``, ``attr_type``) pair.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     attr1: pak.Int8
        ...     attr2: pak.Int16
        ...
        >>> for attr, attr_type in MyPacket.enumerate_field_types():
        ...     print(f"{attr}: {attr_type.__name__}")
        ...
        attr1: Int8
        attr2: Int16
        """

        return cls._fields.items()

    def enumerate_field_values(self):
        """Enumerates the values of the fields of the :class:`Packet`.

        Returns
        -------
        iterable
            Each element of the iterable is a (``attr_name``, ``attr_value``) pair.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     attr1: pak.Int8
        ...     attr2: pak.Int16
        ...
        >>> p = MyPacket(attr1=1, attr2=2)
        >>> for attr, value in p.enumerate_field_values():
        ...     print(f"{attr}: {value}")
        ...
        attr1: 1
        attr2: 2
        """

        for attr in self._fields:
            yield attr, getattr(self, attr)

    def enumerate_field_types_and_values(self):
        """Enumerates the :class:`Types <.Type>` and values of the fields of the :class:`Packet`.

        Returns
        -------
        iterable
            Each element of the iterable is a (``attr_name``, ``attr_type``, ``attr_value``) triplet.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     attr1: pak.Int8
        ...     attr2: pak.Int16
        ...
        >>> p = MyPacket(attr1=1, attr2=2)
        >>> for attr, attr_type, value in p.enumerate_field_types_and_values():
        ...     print(f"{attr}: {attr_type.__name__}; {value}")
        ...
        attr1: Int8; 1
        attr2: Int16; 2
        """

        for attr, attr_type in self.enumerate_field_types():
            yield attr, attr_type, getattr(self, attr)

    @classmethod
    def size(cls):
        """Gets the cumulative size of the fields of the :class:`Packet`.

        Returns
        -------
        :class:`int`
            The cumulative size of the fields of the :class:`Packet`.

        Raises
        ------
        :exc:`TypeError`
            If the size of the :class:`Packet` can't be determined.

        Examples
        --------
        >>> import pak
        >>> class MyPacket(pak.Packet):
        ...     array:   pak.Int16[2]
        ...     float64: pak.Float64
        ...
        >>> MyPacket.size()
        12
        """

        return sum(attr_type.size() for _, attr_type in cls.enumerate_field_types())

    def __eq__(self, other):
        if self._fields != other._fields:
            return False

        return all(
            value == other_value
            for (_, value), (_, other_value) in
            zip(self.enumerate_field_values(), other.enumerate_field_values())
        )

    def __repr__(self):
        return (
            f"{type(self).__name__}("
            f"{', '.join(f'{attr}={repr(value)}' for attr, value in self.enumerate_field_values())}"
            f")"
        )

# Only automatically called for subclasses
# so we need to call it manually here.
Packet._init_fields_from_annotations()

class GenericPacket(Packet):
    """A generic collection of data.

    Reads all of the data in the buffer passed to it.
    """

    data: RawByte[None]
