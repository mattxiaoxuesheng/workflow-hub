package top.hardway.publisher;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class PublisherUrlPolicyTest {
    @Test
    public void acceptsPublisherHttpsPages() {
        assertTrue(PublisherUrlPolicy.isAllowed("https://stocklab.hardway.top/publisher/"));
        assertTrue(PublisherUrlPolicy.isAllowed("https://stocklab.hardway.top/publisher/article?id=1"));
    }

    @Test
    public void rejectsCleartextAndOtherHosts() {
        assertFalse(PublisherUrlPolicy.isAllowed("http://stocklab.hardway.top/publisher/"));
        assertFalse(PublisherUrlPolicy.isAllowed("https://example.com/publisher/"));
        assertFalse(PublisherUrlPolicy.isAllowed("https://stocklab.hardway.top.evil.example/publisher/"));
    }

    @Test
    public void rejectsOtherPathsCredentialsAndPorts() {
        assertFalse(PublisherUrlPolicy.isAllowed("https://stocklab.hardway.top/"));
        assertFalse(PublisherUrlPolicy.isAllowed("https://user@stocklab.hardway.top/publisher/"));
        assertFalse(PublisherUrlPolicy.isAllowed("https://stocklab.hardway.top:443/publisher/"));
    }
}
