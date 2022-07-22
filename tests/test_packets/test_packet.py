import pak
import pytest

class StringToIntDynamicValue(pak.DynamicValue):
    _type = str

    _enabled = False

    def __init__(self, string):
        self.string = string

    def get(self, *, ctx=None):
        return int(self.string)

class BasicPacket(pak.Packet):
    attr1: pak.Int8
    attr2: pak.Int16

def test_packet():
    assert isinstance(BasicPacket.attr1, pak.Int8)

    p = BasicPacket()
    assert p.attr1 == 0 and p.attr2 == 0

    # Test deleting fields works.
    del p.attr1

    pak.test.packet_behavior(
        (BasicPacket(attr1=0, attr2=1), b"\x00\x01\x00"),
    )

    assert BasicPacket().size() == 3

    assert BasicPacket(attr1=0, attr2=1) == BasicPacket(attr1=0, attr2=1)
    assert BasicPacket(attr1=0, attr2=1) != BasicPacket(attr1=1, attr2=0)

    assert repr(BasicPacket(attr1=0, attr2=1)) == "BasicPacket(attr1=0, attr2=1)"

    with pytest.raises(TypeError, match="Unexpected keyword arguments"):
        BasicPacket(test=0)

def test_packet_context():
    assert hash(pak.Packet.Context()) == hash(pak.Packet.Context())

    with pytest.raises(TypeError, match="__hash__"):
        class MyContext(pak.Packet.Context):
            pass

    with pytest.raises(TypeError, match="__hash__"):
        class MyContext(pak.Packet.Context):
            # This class says it can't be hashed (in the standard way)
            # but still provides its own __hash__ member.
            __hash__ = None

    with pytest.raises(TypeError, match="__eq__"):
        class MyContext(pak.Packet.Context):
            __hash__ = pak.Packet.Context

    ctx = pak.Packet.Context()
    with pytest.raises(TypeError, match="immutable"):
        ctx.attr = "test"

    assert pak.Packet.Context() == pak.Packet.Context()
    assert pak.Packet.Context() != object()

    class MyContext(pak.Packet.Context):
        def __init__(self, attr):
            self.attr = attr

            super().__init__()

        def __hash__(self):
            return hash(self.attr)

        def __eq__(self, other):
            return self.attr == other.attr

    ctx = MyContext("test")
    with pytest.raises(TypeError, match="immutable"):
        ctx.attr = "new"

    class MyPacket(pak.Packet):
        field: pak.Int8

        Context = MyContext

    # 'MyPacket.Context' requires an argument so default constructing won't work.
    with pytest.raises(TypeError, match="argument"):
        MyPacket()

    # Test that a context isn't needed when fields are supplied.
    assert MyPacket(field=1).field == 1

def test_reserved_field():
    with pytest.raises(pak.ReservedFieldError, match="ctx"):
        class TestReservedField(pak.Packet):
            ctx: pak.Int8

def test_typelike_attr():
    pak.Type.register_typelike(int, lambda x: pak.Int8)

    class TestTypelike(pak.Packet):
        attr: 1

    pak.test.packet_behavior(
        (TestTypelike(attr=5), b"\x05"),
    )

    pak.Type.unregister_typelike(int)

def test_packet_property():
    class TestProperty(pak.Packet):
        prop: pak.Int8

        @property
        def prop(self):
            return self._prop

        @prop.setter
        def prop(self, value):
            self._prop = int(value)

    p = TestProperty()
    assert p.prop == 0

    pak.test.packet_behavior(
        (TestProperty(prop=1), b"\x01"),
    )

    p = TestProperty(prop=1.5)
    assert p.prop == 1

    class TestReadOnly(pak.Packet):
        read_only: pak.Int8

        @property
        def read_only(self):
            return 1

    p = TestReadOnly()
    assert p.read_only == 1

    pak.test.packet_behavior(
        (TestReadOnly(), b"\x01"),
    )

    with pytest.raises(AttributeError):
        p.read_only = 2

    with pytest.raises(AttributeError):
        TestReadOnly(read_only=2)

def test_packet_inheritance():
    class TestParent(pak.Packet):
        test: pak.Int8

    class TestChildBasic(TestParent):
        pass

    class TestChildOverride(TestParent):
        other: pak.Int8

    # Fields will get passed down
    assert list(TestChildBasic.enumerate_field_types())    == [("test", pak.Int8)]
    assert list(TestChildOverride.enumerate_field_types()) == [("test", pak.Int8), ("other", pak.Int8)]

    assert TestChildBasic()    == TestParent()
    assert TestChildOverride() != TestParent()

    pak.test.packet_behavior(
        (
            TestChildBasic(test=1),

            b"\x01"
        ),

        (
            TestChildOverride(test=1, other=2),

            b"\x01\x02"
        ),
    )

    with pytest.raises(pak.DuplicateFieldError, match="test"):
        class TestDuplicateField(TestParent):
            test: pak.Int8

def test_packet_multiple_inheritance():
    class FirstParent(pak.Packet):
        first: pak.Int8

    class SecondParent(pak.Packet):
        second: pak.Int16

    class Child(FirstParent, SecondParent):
        child: pak.Int32

    assert list(Child.enumerate_field_types()) == [
        ("first",  pak.Int8),
        ("second", pak.Int16),
        ("child",  pak.Int32),
    ]

    pak.test.packet_behavior(
        (
            Child(first=1, second=2, child=3),

            b"\x01\x02\x00\x03\x00\x00\x00"
        ),
    )

    assert Child() != FirstParent()
    assert Child() != SecondParent()

    with pytest.raises(pak.DuplicateFieldError, match="first"):
        class TestDuplicateFirstField(FirstParent, SecondParent):
            first: pak.Int64

    with pytest.raises(pak.DuplicateFieldError, match="second"):
        class TestDuplicateSecondField(FirstParent, SecondParent):
            second: pak.Int64

    class DuplicateFirstParent(pak.Packet):
        test: pak.Int8

    class DuplicateSecondParent(pak.Packet):
        test: pak.Int16

    with pytest.raises(pak.DuplicateFieldError, match="test"):
        class TestDuplicateFieldFromParents(DuplicateFirstParent, DuplicateSecondParent):
            pass

def test_header():
    class Test(pak.Packet):
        class Header(pak.Packet.Header):
            size: pak.UInt8

        byte:  pak.Int8
        short: pak.Int16

    pak.test.packet_behavior(
        (Test.Header(size=3), b"\x03"),
    )

    assert Test().header() == Test.Header(size=3)

    assert Test(byte=1, short=2).pack() == b"\x03\x01\x02\x00"

    with pytest.raises(TypeError, match="fields"):
        Test.Header(Test(), size=2)

    with pytest.raises(TypeError, match="header"):
        class TestHeaderWithHeader(pak.Packet):
            class Header(pak.Packet.Header):
                class Header(pak.Packet.Header):
                    pass

def test_header_correct_context():
    class Test(pak.Packet):
        class Context(pak.Packet.Context):
            __hash__ = pak.Packet.Context.__hash__
            __eq__   = pak.Packet.Context.__eq__

        def check_ctx(self, *, ctx):
            # Make sure we receive the context for 'Test',
            # and not for 'Test.Header', which would just be
            # 'Packet.Context'.
            return isinstance(ctx, Test.Context)

        class Header(pak.Packet.Header):
            check_ctx: pak.Bool

    assert Test().header().check_ctx

def test_id():
    class TestEmpty(pak.Packet):
        pass

    assert TestEmpty.id() is None
    pak.test.packet_behavior(
        (TestEmpty(), b""),
    )

    assert TestEmpty.Header.unpack(b"test") == pak.Packet.Header()

    class TestStaticId(pak.Packet):
        class Header(pak.Packet.Header):
            id: pak.Int8

        id = 1

    assert TestStaticId.id()     == 1
    assert TestStaticId().pack() == b"\x01"

    assert TestStaticId.Header.unpack(b"\x02") == TestStaticId.Header(id=2)

    with StringToIntDynamicValue.context():
        class TestDynamicId(pak.Packet):
            class Header(pak.Packet.Header):
                id: pak.Int8

            id = "1"

        assert TestDynamicId.id()     == 1
        assert TestDynamicId().pack() == b"\x01"

        assert TestDynamicId.Header.unpack(b"\x02") == TestDynamicId.Header(id=2)

def test_packet_size():
    class StaticPacket(pak.Packet):
        field: pak.UInt8

    assert StaticPacket.size()   == 1
    assert StaticPacket().size() == 1

    class DynamicPacket(pak.Packet):
        field: pak.ULEB128

    with pytest.raises(pak.NoStaticSizeError):
        DynamicPacket.size()

    assert DynamicPacket().size() == 1

def test_subclass_id():
    class Root(pak.Packet):
        pass

    class Child1(Root):
        id = 0

    class Child2(Root):
        id = 1

    class GrandChild1(Child1):
        id = 2

    assert Root.subclass_with_id(0) is Child1
    assert Root.subclass_with_id(1) is Child2
    assert Root.subclass_with_id(2) is GrandChild1
    assert Root.subclass_with_id(3) is None

test_generic = pak.test.packet_behavior_func(
    (pak.GenericPacket(data=b"\xAA\xBB\xCC"), b"\xAA\xBB\xCC"),
)
