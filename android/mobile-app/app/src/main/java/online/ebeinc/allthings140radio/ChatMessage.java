package online.ebeinc.allthings140radio;

public final class ChatMessage {
    public final String id;
    public final String name;
    public final String text;
    public final long timestamp;
    public final String color;
    public final boolean verified;
    public final String senderId;
    public final boolean isNotice;

    public ChatMessage(String id, String name, String text, long timestamp, String color, boolean verified, String senderId, boolean isNotice) {
        this.id = id != null ? id : String.valueOf(timestamp);
        this.name = name != null ? name : "Listener";
        this.text = text != null ? text : "";
        this.timestamp = timestamp > 0 ? timestamp : System.currentTimeMillis();
        this.color = color != null ? color : "purple";
        this.verified = verified;
        this.senderId = senderId != null ? senderId : "";
        this.isNotice = isNotice;
    }

    public static ChatMessage systemNotice(String text) {
        return new ChatMessage("notice-" + System.currentTimeMillis(), "SYSTEM", text, System.currentTimeMillis(), "orange", false, "", true);
    }
}
