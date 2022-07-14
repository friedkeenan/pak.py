import pak
import pytest

class StringToIntDynamicValue(pak.DynamicValue):
    _type = str

    _enabled = False

    def __init__(self, string):
        self.string = string

    def get(self, *, ctx=None):
        return int(self.string)

def test_type_context():
    class MyPacketContext(pak.Packet.Context):
        def __init__(self, attr):
            self.attr = attr

            super().__init__()

        def __hash__(self):
            return hash(self.attr)

    p          = pak.Packet()
    packet_ctx = MyPacketContext("test")
    type_ctx   = p.type_ctx(packet_ctx)

    assert type_ctx.packet     is p
    assert type_ctx.packet_ctx is packet_ctx

    assert type_ctx.attr == "test"

    with pytest.raises(AttributeError):
        type_ctx.test

    with pytest.raises(AttributeError):
        pak.Type.Context().test

    with pytest.raises(TypeError, match="immutable"):
        type_ctx.packet = None

def test_typelike():
    assert pak.Type.is_typelike(pak.Int8)
    assert pak.Type(pak.Int8) is pak.Int8

    pak.Type.register_typelike(int, lambda x: pak.Int8)

    assert pak.Type.is_typelike(1)
    assert pak.Type(1) is pak.Int8

    pak.Type.unregister_typelike(int)

    assert not pak.Type.is_typelike(1)
    with pytest.raises(TypeError, match="is not typelike"):
        pak.Type(1)

def test_prepare_types():
    @pak.Type.prepare_types
    def test(x, y: pak.Type, *args: pak.Type, **kwargs: pak.Type):
        assert issubclass(y, pak.Type)
        assert all(issubclass(arg, pak.Type) for arg in args)
        assert all(issubclass(value, pak.Type) for value in kwargs.values())

    # Nones will be converted to EmptyType
    test(1, None, None, None, test=None, other_test=None)

def test_static_size():
    class TestStaticSize(pak.Type):
        _size = 4

    assert TestStaticSize.size() == 4

def test_classmethod_size():
    class TestClassmethodSize(pak.Type):
        @classmethod
        def _size(cls, value, *, ctx):
            if value is pak.Type.STATIC_SIZE:
                return None

            return value * 2;

    assert TestClassmethodSize.size(5) == 10

    with pytest.raises(pak.NoStaticSizeError, match="static size"):
        TestClassmethodSize.size()

def test_dynamic_value_size():
    with StringToIntDynamicValue.context():
        class TestSize(pak.Type):
            _size = "1"

        assert TestSize.size() == 1

def test_no_size():
    class Test(pak.EmptyType):
        _size = None

    with pytest.raises(pak.NoStaticSizeError, match="static size"):
        Test.size()

def test_static_alignment():
    class Test(pak.Type):
        _alignment = 64

    assert Test.alignment() == 64

def test_no_alignment():
    class Test(pak.Type):
        _alignment = None

    with pytest.raises(TypeError, match="alignment"):
        Test.alignment()

def test_classmethod_alignment():
    class Test(pak.Type):
        @classmethod
        def _alignment(cls, *, ctx):
            return 64

    assert Test.alignment() == 64

def test_dynamic_value_alignment():
    with StringToIntDynamicValue.context():
        class Test(pak.Type):
            _alignment = "64"

        assert Test.alignment() == 64

def test_alignment_padding():
    assert pak.Type.alignment_padding_lengths(
        pak.Int16,
        pak.Int32,
        pak.Int8,

        total_alignment = 4,
    ) == [
        2,
        0,
        3,
    ]

def test_static_default():
    class Test(pak.Type):
        _default = [1, 2, 3]

    assert Test.default() == [1, 2, 3]
    assert Test.default() is not Test._default

def test_no_default():
    class Test(pak.EmptyType):
        _default = None

    with pytest.raises(TypeError, match="default value"):
        Test.default()

def test_classmethod_default():
    SENTINEL = pak.util.UniqueSentinel()

    class Test(pak.Type):
        @classmethod
        def _default(cls, *, ctx):
            return SENTINEL

    assert Test.default() is SENTINEL

def test_dynamic_value_default():
    with StringToIntDynamicValue.context():
        class TestDefault(pak.Type):
            _default = "1"

        assert TestDefault.default() == 1

def test_cached_make_type():
    class TestCall(pak.Type):
        @classmethod
        def _call(cls):
            return cls.make_type("blah")

    assert TestCall() is TestCall()

def test_not_implemented_methods():
    with pytest.raises(TypeError, match="initialized"):
        pak.Type.__init__(object())

    with pytest.raises(NotImplementedError):
        pak.Type.unpack(b"")

    with pytest.raises(NotImplementedError):
        pak.Type.pack(None)

    with pytest.raises(NotImplementedError):
        pak.Type._call()
