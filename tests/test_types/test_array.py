import io
import pak
import pytest

def test_array():
    assert issubclass(pak.Int8[2], pak.Array)

    pak.test.type_behavior(
        pak.Int8[2],

        ([0, 1], b"\x00\x01"),

        static_size = 2,
        alignment   = 1,
        default     = [0, 0],
    )

    pak.test.type_behavior(
        pak.Int8[pak.Int8],

        ([0, 1], b"\x02\x00\x01"),
        ([],     b"\x00"),

        static_size = None,
        default     = [],
    )

    pak.test.type_behavior(
        pak.Int8[None],

        ([0, 1, 2], b"\x00\x01\x02"),

        static_size = None,
        default     = [],
    )

    assert pak.Int8[2].pack([1]) == b"\x01\x00"

    # Conveniently testing string sizes will also
    # test function sizes.
    assert pak.Int8["test"].has_size_function()

    class TestAttr(pak.Packet):
        test:  pak.Int8
        array: pak.Int8["test"]

    assert TestAttr(test=2).array == [0, 0]

    # Test you can properly delete array attributes.
    p = TestAttr()
    del p.array

    pak.test.packet_behavior(
        (TestAttr(test=2, array=[0, 1]), b"\x02\x00\x01"),
    )

    ctx_len_2 = TestAttr(test=2, array=[0, 1]).type_ctx(None)
    pak.test.type_behavior(
        pak.Int8["test"],

        ([0, 1], b"\x00\x01"),

        static_size = 2,
        alignment   = 1,
        default     = [0, 0],
        ctx         = ctx_len_2,
    )

    with pytest.raises(Exception):
        pak.Int8[2].unpack(b"\x00")

    with pytest.raises(Exception):
        pak.Int8[pak.Int8].unpack(b"\x01")

    with pytest.raises(Exception):
        TestAttr.unpack(b"\x01")
