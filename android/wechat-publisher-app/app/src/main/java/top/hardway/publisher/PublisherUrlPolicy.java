package top.hardway.publisher;

import java.net.URI;

public final class PublisherUrlPolicy {
    private static final String HOST = "stocklab.hardway.top";
    private static final String BASE_PATH = "/publisher";

    private PublisherUrlPolicy() {}

    public static boolean isAllowed(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        try {
            URI uri = URI.create(value);
            if (!"https".equalsIgnoreCase(uri.getScheme())) {
                return false;
            }
            if (!HOST.equalsIgnoreCase(uri.getHost())) {
                return false;
            }
            if (uri.getUserInfo() != null || uri.getPort() != -1) {
                return false;
            }
            String path = uri.getPath();
            return BASE_PATH.equals(path) || (path != null && path.startsWith(BASE_PATH + "/"));
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }
}
