package online.ebeinc.allthings140radio;

final class VersionUtils {
    private VersionUtils() {}

    static int compare(String left, String right) {
        int[] a = parts(left);
        int[] b = parts(right);
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {
            int av = i < a.length ? a[i] : 0;
            int bv = i < b.length ? b[i] : 0;
            if (av != bv) return Integer.compare(av, bv);
        }
        return 0;
    }

    private static int[] parts(String value) {
        if (value == null) return new int[]{0};
        String normalized = value.trim().replaceFirst("^[vV]", "");
        String[] raw = normalized.split("[.-]");
        int[] result = new int[raw.length == 0 ? 1 : raw.length];
        for (int i = 0; i < raw.length; i++) {
            String digits = raw[i].replaceAll("[^0-9].*$", "").replaceAll("[^0-9]", "");
            if (digits.isEmpty()) {
                result[i] = 0;
            } else {
                try {
                    result[i] = Integer.parseInt(digits);
                } catch (NumberFormatException ignored) {
                    result[i] = Integer.MAX_VALUE;
                }
            }
        }
        return result;
    }
}
