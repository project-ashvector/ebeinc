package online.ebeinc.talkietalkie;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

public class TalkieListeningService extends Service {
    private static final String CHANNEL_ID = "ebe_talkie_listening";
    private static final int NOTIFICATION_ID = 1401;
    public static final String ACTION_STOP = "online.ebeinc.talkietalkie.STOP_LISTENING";

    private PowerManager.WakeLock wakeLock;

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager != null) {
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "EBETalkieTalkie:Listening");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        startForeground(NOTIFICATION_ID, buildNotification());
        return START_STICKY;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "EBE Talkie Talkie",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Keeps the family walkie-talkie channel listening in the background.");
            channel.setShowBadge(false);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification() {
        Intent openIntent = new Intent(this, EnhancedMainActivity.class);
        openIntent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openPending = PendingIntent.getActivity(
                this,
                1401,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Intent stopIntent = new Intent(this, TalkieListeningService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPending = PendingIntent.getService(
                this,
                1402,
                stopIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setSmallIcon(R.drawable.ic_stat_talkie)
                .setContentTitle("EBE Talkie Talkie")
                .setContentText("Family channel listening · tap to open")
                .setContentIntent(openPending)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .addAction(new Notification.Action.Builder(R.drawable.ic_stat_talkie, "Stop", stopPending).build())
                .build();
    }

    @Override
    public void onDestroy() {
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
