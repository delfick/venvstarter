# coding: spec

from venvstarter import Version

describe "Version":
    it "can create from different values":
        assert Version(3).version == (3, 0, 0)
        assert Version(3.7).version == (3, 7, 0)
        assert Version(3.78).version == (3, 78, 0)
        assert Version("3.7.3").version == (3, 7, 3)

        assert Version(Version(3)).version == (3, 0, 0)
        assert Version(Version(3.7)).version == (3, 7, 0)
        assert Version(Version("3.7.30")).version == (3, 7, 30)

        assert Version((3,)).version == (3, 0, 0)
        assert Version((3, 7)).version == (3, 7, 0)
        assert Version((3, 7, 3)).version == (3, 7, 3)

    it "can be made to ignore the patch":
        assert Version(3, without_patch=True).version == (3, 0, 0)
        assert Version(3.7, without_patch=True).version == (3, 7, 0)
        assert Version(3.79, without_patch=True).version == (3, 79, 0)
        assert Version("3.7.3", without_patch=True).version == (3, 7, 0)

        assert Version(Version(3), without_patch=True).version == (3, 0, 0)
        assert Version(Version(3.7), without_patch=True).version == (3, 7, 0)
        assert Version(Version("3.7.30"), without_patch=True).version == (3, 7, 0)

        assert Version((3,), without_patch=True).version == (3, 0, 0)
        assert Version((3, 7), without_patch=True).version == (3, 7, 0)
        assert Version((3, 7, 3), without_patch=True).version == (3, 7, 0)

    it "can be turned into a string":
        assert str(Version(3)) == "3.0.0"
        assert str(Version("3.7")) == "3.7.0"
        assert str(Version("3.7.30")) == "3.7.30"
        assert str(Version("3.7.30", without_patch=True)) == "3.7.0"

    it "can be turned into a repr":
        assert repr(Version(3)) == "<Version 3.0.0>"
        assert repr(Version("3.7")) == "<Version 3.7.0>"
        assert repr(Version("3.7.30")) == "<Version 3.7.30>"
        assert repr(Version("3.7.30", without_patch=True)) == "<Version 3.7.0>"

    it "can be compared":
        v3 = Version(3)
        v35 = Version("3.5")
        v35_2 = Version("3.5.2")
        v37 = Version(3.7)
        v37_2 = Version("3.7.2")
        v37_4 = Version("3.7.4")
        v37_9 = Version("3.7.9")
        v4 = Version(4)

        assert v3 == Version(3)
        assert v3 != v4
        assert v3 != v35
        assert v37 != v37_2
        assert v37_2 != v37_9

        assert v3 <= Version(3)
        assert v3 >= Version(3)

        assert v3 <= Version(4)
        assert not v3 <= Version(2)
        assert not v3 < Version(2)

        assert v3 >= Version(2)
        assert v3 > Version(2)
        assert not v3 > Version(4)

        assert v37 < v37_2
        assert v37_2 >= v37_2
        assert v37_4 > v37_2
        assert not v37_9 < v37_4
        assert v37_9 > v37_4

        assert v35_2 < v37_2
        assert not v35_2 > v37_2
