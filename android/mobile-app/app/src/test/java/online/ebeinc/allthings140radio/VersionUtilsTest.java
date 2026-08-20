package online.ebeinc.allthings140radio;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class VersionUtilsTest {
    @Test public void equalVersionsCompareEqual() {
        assertEquals(0, VersionUtils.compare("1.3.0", "v1.3.0"));
    }

    @Test public void newerPatchComparesGreater() {
        assertTrue(VersionUtils.compare("1.3.1", "1.3.0") > 0);
        assertTrue(VersionUtils.compare("1.3.2", "1.3.1") > 0);
    }

    @Test public void currentVersionMatches() {
        assertEquals(0, VersionUtils.compare("1.3.1", "1.3.1"));
        assertEquals(0, VersionUtils.compare("v1.3.1", "1.3.1"));
    }

    @Test public void missingPatchIsZero() {
        assertEquals(0, VersionUtils.compare("1.3", "1.3.0"));
    }

    @Test public void olderRemoteDoesNotLookNewer() {
        assertTrue(VersionUtils.compare("1.3.0", "1.3.1") < 0);
        assertTrue(VersionUtils.compare("1.2.9", "1.3.1") < 0);
    }
}
