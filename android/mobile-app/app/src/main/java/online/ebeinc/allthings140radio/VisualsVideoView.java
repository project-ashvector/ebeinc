package online.ebeinc.allthings140radio;

import android.content.Context;
import android.graphics.Outline;
import android.graphics.SurfaceTexture;
import android.media.MediaPlayer;
import android.net.Uri;
import android.util.AttributeSet;
import android.util.Log;
import android.view.Gravity;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.ViewOutlineProvider;
import android.widget.FrameLayout;

/**
 * Isolated muted video player for ALLTHINGS140 visuals loop.
 * Plays silently with zero interference with the primary RadioService audio.
 */
public final class VisualsVideoView extends FrameLayout implements TextureView.SurfaceTextureListener {
    private static final String TAG = "VisualsVideoView";
    private static final float ASPECT_RATIO = 16f / 9f;

    private TextureView textureView;
    private Surface surface;
    private MediaPlayer mediaPlayer;
    private boolean isSurfaceReady = false;
    private boolean isPrepared = false;
    private boolean playWhenReady = true;

    public VisualsVideoView(Context context) {
        super(context);
        init(context);
    }

    public VisualsVideoView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init(context);
    }

    public VisualsVideoView(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init(context);
    }

    private void init(Context context) {
        setBackgroundResource(R.drawable.panel);
        
        final float density = getResources().getDisplayMetrics().density;
        final float cornerRadius = 14f * density;
        setOutlineProvider(new ViewOutlineProvider() {
            @Override
            public void getOutline(View view, Outline outline) {
                outline.setRoundRect(0, 0, view.getWidth(), view.getHeight(), cornerRadius);
            }
        });
        setClipToOutline(true);

        textureView = new TextureView(context);
        textureView.setSurfaceTextureListener(this);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT, Gravity.CENTER);
        addView(textureView, lp);
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int width = MeasureSpec.getSize(widthMeasureSpec);
        if (width > 0) {
            int height = Math.round(width / ASPECT_RATIO);
            int exactHeightSpec = MeasureSpec.makeMeasureSpec(height, MeasureSpec.EXACTLY);
            super.onMeasure(widthMeasureSpec, exactHeightSpec);
        } else {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec);
        }
    }

    @Override
    public void onSurfaceTextureAvailable(SurfaceTexture surfaceTexture, int width, int height) {
        isSurfaceReady = true;
        surface = new Surface(surfaceTexture);
        initMediaPlayer();
    }

    @Override
    public void onSurfaceTextureSizeChanged(SurfaceTexture surfaceTexture, int width, int height) {
    }

    @Override
    public boolean onSurfaceTextureDestroyed(SurfaceTexture surfaceTexture) {
        isSurfaceReady = false;
        releaseMediaPlayer();
        if (surface != null) {
            surface.release();
            surface = null;
        }
        return true;
    }

    @Override
    public void onSurfaceTextureUpdated(SurfaceTexture surfaceTexture) {
    }

    private void initMediaPlayer() {
        if (!isSurfaceReady || surface == null || !surface.isValid()) return;
        if (mediaPlayer != null) return;

        try {
            mediaPlayer = new MediaPlayer();
            mediaPlayer.setSurface(surface);
            mediaPlayer.setVolume(0.0f, 0.0f); // 100% MUTED at all times
            mediaPlayer.setLooping(true);

            Uri videoUri = Uri.parse("android.resource://" + getContext().getPackageName() + "/" + R.raw.visuals_loop);
            mediaPlayer.setDataSource(getContext(), videoUri);

            mediaPlayer.setOnPreparedListener(mp -> {
                isPrepared = true;
                if (playWhenReady) {
                    try {
                        mp.start();
                    } catch (Exception e) {
                        Log.w(TAG, "Error starting visuals video", e);
                    }
                }
            });

            mediaPlayer.setOnErrorListener((mp, what, extra) -> {
                Log.w(TAG, "MediaPlayer error: what=" + what + " extra=" + extra);
                releaseMediaPlayer();
                return true;
            });

            mediaPlayer.prepareAsync();
        } catch (Exception e) {
            Log.e(TAG, "Failed to initialize visual MediaPlayer", e);
            releaseMediaPlayer();
        }
    }

    public void startPlayback() {
        playWhenReady = true;
        if (mediaPlayer != null && isPrepared) {
            try {
                if (!mediaPlayer.isPlaying()) {
                    mediaPlayer.start();
                }
            } catch (Exception e) {
                Log.w(TAG, "Error starting playback", e);
            }
        } else if (isSurfaceReady && mediaPlayer == null) {
            initMediaPlayer();
        }
    }

    public void pausePlayback() {
        playWhenReady = false;
        if (mediaPlayer != null && isPrepared) {
            try {
                if (mediaPlayer.isPlaying()) {
                    mediaPlayer.pause();
                }
            } catch (Exception e) {
                Log.w(TAG, "Error pausing playback", e);
            }
        }
    }

    public void releasePlayer() {
        playWhenReady = false;
        releaseMediaPlayer();
    }

    private void releaseMediaPlayer() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.stop();
            } catch (Exception ignored) {}
            try {
                mediaPlayer.reset();
                mediaPlayer.release();
            } catch (Exception ignored) {}
            mediaPlayer = null;
        }
        isPrepared = false;
    }
}
