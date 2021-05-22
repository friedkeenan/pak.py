import io
import pytest
from pak import *

from ..util import assert_type_marshal, assert_packet_marshal

def test_padding_array():
    buf = io.BytesIO(b"\x00\x00\x01\x00\x00")
    assert Padding[2].unpack(buf) is None
    assert buf.tell() == 2

    assert Padding[Int8].unpack(buf) is None
    assert buf.tell() == 4

    buf = io.BytesIO(b"test data")
    assert Padding[None].unpack(buf) is None
    assert buf.tell() == 9

    class TestAttr(Packet):
        test: Int8
        array: Padding["test"]

    buf = io.BytesIO(b"\x02\xaa\xbb\xcc")
    p   = TestAttr.unpack(buf)
    assert p.test == 2 and p.array is None
    assert buf.tell() == 3

    assert Padding[2].pack("whatever value")    == b"\x00\x00"
    assert Padding[Int8].pack("whatever value") == b"\x00"

    with pytest.raises(util.BufferOutOfDataError):
        Padding[2].unpack(b"\x00")

    with pytest.raises(util.BufferOutOfDataError):
        Padding[Int8].unpack(b"\x01")

    with pytest.raises(util.BufferOutOfDataError):
        TestAttr.unpack(b"\x01")

def test_raw_byte_array():
    assert isinstance(RawByte[1].unpack(b"\x00"), bytearray)

    # Values are actually bytearrays but will still
    # have equality with bytes objects.
    assert_type_marshal(
        RawByte[2],
        (b"\xaa\xbb", b"\xaa\xbb"),
    )

    assert_type_marshal(
        RawByte[Int8],
        (b"\xaa\xbb", b"\x02\xaa\xbb"),
        (b"",         b"\x00"),
    )

    assert_type_marshal(
        RawByte[None],
        (b"\xaa\xbb\xcc", b"\xaa\xbb\xcc"),
    )

    class TestAttr(Packet):
        test: Int8
        array: RawByte["test"]

    assert_packet_marshal(
        (TestAttr(test=2, array=b"\x00\x01"), b"\x02\x00\x01"),
    )

    assert RawByte[2].pack(b"\xaa\xbb\xcc")          == b"\xaa\xbb"
    assert RawByte[Int8].unpack(b"\x02\xaa\xbb\xcc") == b"\xaa\xbb"

    with pytest.raises(util.BufferOutOfDataError):
        RawByte[2].unpack(b"\x00")

    with pytest.raises(util.BufferOutOfDataError):
        RawByte[Int8].unpack(b"\x01")

    with pytest.raises(util.BufferOutOfDataError):
        TestAttr.unpack(b"\x01")

def test_array():
    assert issubclass(Int8[2], Array)

    assert_type_marshal(
        Int8[2],
        ([0, 1], b"\x00\x01"),
    )

    assert_type_marshal(
        Int8[Int8],
        ([0, 1], b"\x02\x00\x01"),
        ([],     b"\x00"),
    )

    assert_type_marshal(
        Int8[None],
        ([0, 1, 2], b"\x00\x01\x02"),
    )

    # Conveniently testing string sizes will also
    # test function sizes.
    assert Int8["test"].has_size_function()

    class TestAttr(Packet):
        test:  Int8
        array: Int8["test"]

    assert_packet_marshal(
        (TestAttr(test=2, array=[0, 1]), b"\x02\x00\x01"),
    )

    with pytest.raises(Exception):
        Int8[2].unpack(b"\x00")

    with pytest.raises(Exception):
        Int8[Int8].unpack(b"\x01")

    with pytest.raises(Exception):
        TestAttr.unpack(b"\x01")