# coding: spec

from venvstarter import Version

describe "Version":
    it "can create from different values":
        assert Version(3).version == (3, 0, 0)
        assert Version(3.6).version == (3, 6, 0)
        assert Version(3.68).version == (3, 68, 0)
        assert Version("3.6.3").version == (3, 6, 3)

        assert Version(Version(3)).version == (3, 0, 0)
        assert Version(Version(3.6)).version == (3, 6, 0)
        assert Version(Version("3.6.30")).version == (3, 6, 30)

        assert Version((3,)).version == (3, 0, 0)
        assert Version((3, 6)).version == (3, 6, 0)
        assert Version((3, 6, 3)).version == (3, 6, 3)

    it "can be made to ignore the patch":
        assert Version(3, without_patch=True).version == (3, 0, 0)
        assert Version(3.6, without_patch=True).version == (3, 6, 0)
        assert Version(3.68, without_patch=True).version == (3, 68, 0)
        assert Version("3.6.3", without_patch=True).version == (3, 6, 0)

        assert Version(Version(3), without_patch=True).version == (3, 0, 0)
        assert Version(Version(3.6), without_patch=True).version == (3, 6, 0)
        assert Version(Version("3.6.30"), without_patch=True).version == (3, 6, 0)

        assert Version((3,), without_patch=True).version == (3, 0, 0)
        assert Version((3, 6), without_patch=True).version == (3, 6, 0)
        assert Version((3, 6, 3), without_patch=True).version == (3, 6, 0)

    it "can be turned into a string":
        assert str(Version(3)) == "3.0.0"
        assert str(Version("3.6")) == "3.6.0"
        assert str(Version("3.6.30")) == "3.6.30"
        assert str(Version("3.6.30", without_patch=True)) == "3.6.0"

    it "can be turned into a repr":
        assert repr(Version(3)) == "<Version 3.0.0>"
        assert repr(Version("3.6")) == "<Version 3.6.0>"
        assert repr(Version("3.6.30")) == "<Version 3.6.30>"
        assert repr(Version("3.6.30", without_patch=True)) == "<Version 3.6.0>"

    it "can be compared":
        v3 = Version(3)
        v35 = Version("3.5")
        v35_2 = Version("3.5.2")
        v36 = Version(3.6)
        v36_2 = Version("3.6.2")
        v36_4 = Version("3.6.4")
        v36_9 = Version("3.6.9")
        v4 = Version(4)

        assert v3 == Version(3)
        assert v3 != v4
        assert v3 != v35
        assert v36 != v36_2
        assert v36_2 != v36_9

        assert v3 <= Version(3)
        assert v3 >= Version(3)

        assert v3 <= Version(4)
        assert not v3 <= Version(2)
        assert not v3 < Version(2)

        assert v3 >= Version(2)
        assert v3 > Version(2)
        assert not v3 > Version(4)

        assert v36 < v36_2
        assert v36_2 >= v36_2
        assert v36_4 > v36_2
        assert not v36_9 < v36_4
        assert v36_9 > v36_4

        assert v35_2 < v36_2
        assert not v35_2 > v36_2
