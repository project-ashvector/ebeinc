package online.ebeinc.talkietalkie;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

/**
 * Android 15+ does not allow a mediaPlayback foreground service to be launched
 * directly from BOOT_COMPLETED. If the phone reboots while a room is armed, we
 * leave the room state intact and post a one-tap reminder to resume it.
 */
public class BootReminderReceiver extends BroadcastReceiver {
    private static final String PREFS = "ebe_talkie_talkie";
    private static final String CHANNEL = "ebe_talkie_boot_resume";
    private static final int ID = 1420;

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!prefs.getBoolean("auto_connect", false)) return;

        if (Build.VERSION.SDK_INT >= 33
                && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL,
                    "Resume room after restart",
                    NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Reminds you to reopen EBE Talkie Talkie after the phone restarts.");
            nm.createNotificationChannel(channel);
        }

        Intent open = new Intent(context, PersistentMainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pending = PendingIntent.getActivity(
                context,
                ID,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String room = prefs.getString("active_room_name", "your room");
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, CHANNEL)
                : new Notification.Builder(context);

        builder.setSmallIcon(R.drawable.ic_stat_talkie)
                .setContentTitle("Resume EBE Talkie Talkie")
                .setContentText("Tap once to resume always-on listening in " + room)
                .setContentIntent(pending)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_REMINDER);

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            builder.setPriority(Notification.PRIORITY_HIGH);
        }
        nm.notify(ID, builder.build());
    }
}
