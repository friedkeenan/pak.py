"""Generic code for :class:`Packets <.Packet>`."""

# This module isn't split up currently because it has
# so few members, but in the event it gets too large,
# it should be split up.

import inspect

from . import util
from .dyn_value import DynamicValue
from .types.type import Type, TypeContext
from .types.misc import RawByte, EmptyType

__all__ = [
    "PacketContext",
    "Packet",
    "GenericPacket",
]

class PacketContext:
    """The context for a :class:`Packet`.

    To be inherited from by users of the library
    for their own contexts.

    Warnings
    --------
    Subclasses must be hashable.
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

    Additionally your attributes can be properties::

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

    _id_type = EmptyType

    # The fields dictionary for 'Packet'.
    #
    # Since 'Packet' has no annotations, and has no parent to fall back on
    # for its fields, we define it here.
    _fields = {}

    @classmethod
    def id(cls, *, ctx=None):
        """Gets the ID of the :class:`Packet`.

        Lots of packet protocols prefix packets with
        an ID to determine what type of packet should
        be read. Unless overridden, :class:`Packet` has
        no meaningful ID.

        How the ID is marshaled can be changed by setting
        the :attr:`_id_type` attribute to the appropriate
        :class:`~.Type`.

        If the :attr:`id` attribute of a subclass is enrolled
        in the :class:`~.DynamicValue` machinery, then its dynamic
        value is returned from this function. Otherwise the value
        of the :attr:`id` attribute is returned.

        .. note::

            The ID of a :class:`Packet` is not checked for
            equality between :class:`Packets <Packet>`.

        Warnings
        --------
        The ID of a :class:`Packet` must be both hashable and equality
        comparable for various facilities involving IDs to work correctly.

        Parameters
        ----------
        ctx : :class:`PacketContext`
            The context for the :class:`Packet`.

        Returns
        -------
        any
            By default returns ``None``, and if the ID is ``None``
            then the :class:`Packet` shouldn't be considered when
            looking up :class:`Packets <Packet>` from their ID.

            Otherwise the ID of the :class:`Packet`.
        """

        return None

    @classmethod
    def _init_fields_from_annotations(cls):
        # In 3.10+ we can use inspect.get_annotations()
        annotations = getattr(cls, "__annotations__", {})
        if len(annotations) == 0:
            # If we don't have our own annotations, fall back on the '_fields' attribute of our parent class.
            return

        cls._fields = {}

        for attr, attr_type in annotations.items():
            real_type = Type(attr_type)

            cls._fields[attr] = real_type

            # Only add the Type descriptor
            # if there isn't already something
            # in its place (like a property).
            if not hasattr(cls, attr):
                descriptor = real_type.descriptor()

                # Set the name manually because __set_name__
                # only gets called on type construction, and
                # furthermore before __init_subclass__ is called.
                descriptor.__set_name__(cls, attr)

                setattr(cls, attr, descriptor)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls._init_fields_from_annotations()

        if not inspect.ismethod(cls.id):
            id = DynamicValue(inspect.getattr_static(cls, "id"))

            if isinstance(id, DynamicValue):
                @classmethod
                def real_id(cls, *, ctx=None):
                    """Gets the ID of the packet."""

                    return id.get(ctx=ctx)
            else:
                @classmethod
                def real_id(cls, *, ctx=None):
                    """Gets the ID of the packet."""

                    return id

            cls.id = real_id

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

        .. note::

            This doesn't unpack the ID, as you need to unpack the ID
            to determine the correct :class:`Packet` in the first place.

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

        .. note::

            This does pack the ID, unlike :meth:`unpack`.

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

        type_ctx  = self.type_ctx(ctx)
        packed_id = self._id_type.pack(self.id(ctx=ctx), ctx=type_ctx)

        return  packed_id + b"".join(
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

        .. note::

            The ID is not included in the size.

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

    @classmethod
    def unpack_id(cls, buf, *, ctx=None):
        """Unpacks the ID of a :class:`Packet`.

        Parameters
        ----------
        buf : file object or :class:`bytes` or :class:`bytearray`
            The buffer containing the raw data.
        ctx: :class:`PacketContext`
            The context for the :class:`Packet`.
        """

        buf = util.file_object(buf)

        return cls._id_type.unpack(buf, ctx=TypeContext(None, ctx=ctx))

    @classmethod
    @util.cache
    def subclasses(cls):
        """Gets the recursive subclasses of the :class:`Packet`.

        Useful for when you have categories of :class:`Packets <Packet>`,
        such as serverbound and clientbound, and so you can have an empty
        class like

        ::

            class ServerboundPacket(Packet):
                pass

        which all serverbound :class:`Packets <Packet>` would inherit from,
        and then use :meth:`subclasses` to automatically get all the
        serverbound :class:`Packets <Packet>`.

        .. note::

            This method is decorated with :func:`util.cache() <.decorators.cache>`. In particular
            this means you can't generate a new subclass after calling this
            and have it be returned from :meth:`subclasses` the next time you
            call it.

        Returns
        -------
        :class:`set`
            The recursive subclasses of the :class:`Packet`.
        """

        return util.subclasses(cls)

    @classmethod
    @util.cache
    def subclass_with_id(cls, id, *, ctx=None):
        """Gets the subclass with the equivalent ID.

        Parameters
        ----------
        id
            The ID of the :class:`Packet`.

            .. seealso::
                :meth:`Packet.id`
        ctx : :class:`PacketContext`
            The context for  the :class:`Packet`.

        Returns
        -------
        subclass of :class:`Packet` or ``None``
            If ``None``, then there is no :class:`Packet` whose
            ID is ``id``. Otherwise returns the appropriate subclass.
        """

        for subclass in cls.subclasses():
            subclass_id = subclass.id(ctx=ctx)
            if subclass_id is not None and subclass_id == id:
                return subclass

        return None

    def __eq__(self, other):
        # ID is not included in equality.

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

class GenericPacket(Packet):
    """A generic collection of data.

    Reads all of the data in the buffer passed to it.
    """

    data: RawByte[None]
