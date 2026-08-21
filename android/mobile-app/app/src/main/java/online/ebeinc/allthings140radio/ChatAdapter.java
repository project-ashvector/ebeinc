package online.ebeinc.allthings140radio;

import android.content.Context;
import android.text.format.DateFormat;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class ChatAdapter extends RecyclerView.Adapter<ChatAdapter.MessageViewHolder> {
    public interface OnMessageActionCallback {
        void onMessageAction(ChatMessage message);
    }

    private final Context context;
    private final List<ChatMessage> allMessages = new ArrayList<>();
    private final List<ChatMessage> visibleMessages = new ArrayList<>();
    private final Set<String> blockedUsers = new HashSet<>();
    private final Set<String> reportedMessageIds = new HashSet<>();
    private OnMessageActionCallback actionCallback;

    public ChatAdapter(Context context) {
        this.context = context;
    }

    public void setActionCallback(OnMessageActionCallback callback) {
        this.actionCallback = callback;
    }

    public void setBlockedUsers(Set<String> blocked) {
        blockedUsers.clear();
        if (blocked != null) blockedUsers.addAll(blocked);
        filterMessages();
    }

    public void blockUser(String userName) {
        if (userName != null) {
            blockedUsers.add(userName.trim().toLowerCase(java.util.Locale.ROOT));
            filterMessages();
        }
    }

    public void blockUserId(String userId) {
        if (userId != null && !userId.trim().isEmpty()) {
            blockedUsers.add("id:" + userId.trim());
            filterMessages();
        }
    }

    public void reportMessage(String messageId) {
        if (messageId != null) {
            reportedMessageIds.add(messageId);
            filterMessages();
        }
    }

    public void setMessages(List<ChatMessage> messages) {
        allMessages.clear();
        if (messages != null) allMessages.addAll(messages);
        filterMessages();
    }

    public void addMessage(ChatMessage message) {
        if (message == null) return;
        allMessages.add(message);
        if (shouldDisplay(message)) {
            visibleMessages.add(message);
            notifyItemInserted(visibleMessages.size() - 1);
        }
    }

    public void removeMessage(String messageId) {
        if (messageId == null) return;
        for (int i = 0; i < visibleMessages.size(); i++) {
            if (messageId.equals(visibleMessages.get(i).id)) {
                visibleMessages.remove(i);
                notifyItemRemoved(i);
                break;
            }
        }
        java.util.Iterator<ChatMessage> iterator = allMessages.iterator();
        while (iterator.hasNext()) {
            if (messageId.equals(iterator.next().id)) iterator.remove();
        }
    }

    public void clearMessages() {
        allMessages.clear();
        visibleMessages.clear();
        notifyDataSetChanged();
    }

    private boolean shouldDisplay(ChatMessage m) {
        if (reportedMessageIds.contains(m.id)) return false;
        if (m.isNotice) return true;
        String lowerName = m.name.trim().toLowerCase(java.util.Locale.ROOT);
        return !blockedUsers.contains(lowerName) && !blockedUsers.contains("id:" + m.senderId);
    }

    private void filterMessages() {
        visibleMessages.clear();
        for (ChatMessage m : allMessages) {
            if (shouldDisplay(m)) {
                visibleMessages.add(m);
            }
        }
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public MessageViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(context).inflate(R.layout.item_chat_message, parent, false);
        return new MessageViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull MessageViewHolder holder, int position) {
        ChatMessage msg = visibleMessages.get(position);
        holder.bind(msg, actionCallback);
    }

    @Override
    public int getItemCount() {
        return visibleMessages.size();
    }

    static class MessageViewHolder extends RecyclerView.ViewHolder {
        private final TextView avatar;
        private final TextView senderName;
        private final TextView time;
        private final TextView body;
        private final View bubble;

        public MessageViewHolder(@NonNull View itemView) {
            super(itemView);
            avatar = itemView.findViewById(R.id.txtAvatar);
            senderName = itemView.findViewById(R.id.txtSenderName);
            time = itemView.findViewById(R.id.txtTime);
            body = itemView.findViewById(R.id.txtMessageBody);
            bubble = itemView.findViewById(R.id.bubbleLayout);
        }

        public void bind(ChatMessage msg, OnMessageActionCallback callback) {
            Context ctx = itemView.getContext();

            if (msg.isNotice) {
                avatar.setVisibility(View.GONE);
                senderName.setText("● SYSTEM NOTICE");
                senderName.setTextColor(ContextCompat.getColor(ctx, R.color.orange));
                time.setVisibility(View.GONE);
                body.setText(msg.text);
                body.setTextColor(ContextCompat.getColor(ctx, R.color.muted));
                itemView.setOnClickListener(null);
                itemView.setOnLongClickListener(null);
                return;
            }

            avatar.setVisibility(View.VISIBLE);
            time.setVisibility(View.VISIBLE);

            String initial = msg.name.isEmpty() ? "?" : msg.name.substring(0, 1).toUpperCase(java.util.Locale.ROOT);
            avatar.setText(initial);

            int avatarDrawable = R.drawable.avatar_purple;
            int nameColor = ContextCompat.getColor(ctx, R.color.purple_neon);

            String color = msg.color.toLowerCase(java.util.Locale.ROOT);
            if ("cyan".equals(color)) {
                avatarDrawable = R.drawable.avatar_cyan;
                nameColor = ContextCompat.getColor(ctx, R.color.chat_cyan);
            } else if ("pink".equals(color)) {
                avatarDrawable = R.drawable.avatar_pink;
                nameColor = ContextCompat.getColor(ctx, R.color.chat_pink);
            } else if ("green".equals(color)) {
                avatarDrawable = R.drawable.avatar_green;
                nameColor = ContextCompat.getColor(ctx, R.color.chat_green);
            } else if ("orange".equals(color)) {
                avatarDrawable = R.drawable.avatar_orange;
                nameColor = ContextCompat.getColor(ctx, R.color.chat_orange);
            }

            avatar.setBackgroundResource(avatarDrawable);

            String displayName = msg.name + (msg.verified ? " ✓" : "");
            senderName.setText(displayName);
            senderName.setTextColor(nameColor);

            java.text.DateFormat df = DateFormat.getTimeFormat(ctx);
            time.setText(df.format(new Date(msg.timestamp)));

            body.setText(msg.text);
            body.setTextColor(ContextCompat.getColor(ctx, R.color.white));

            View.OnClickListener clickListener = v -> {
                if (callback != null) callback.onMessageAction(msg);
            };
            itemView.setOnClickListener(clickListener);
            itemView.setOnLongClickListener(v -> {
                if (callback != null) callback.onMessageAction(msg);
                return true;
            });
        }
    }
}
