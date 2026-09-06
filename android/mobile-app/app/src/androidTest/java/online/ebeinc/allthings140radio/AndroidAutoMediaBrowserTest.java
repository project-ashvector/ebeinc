package online.ebeinc.allthings140radio;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.ComponentName;
import android.content.Context;
import android.media.browse.MediaBrowser;
import android.media.session.MediaController;
import android.os.Handler;
import android.os.Looper;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public final class AndroidAutoMediaBrowserTest {
    @Test public void legacyCarClientCanBrowseAndPlayLiveStation() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        CountDownLatch connected = new CountDownLatch(1);
        CountDownLatch childrenLoaded = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicReference<MediaBrowser> browserReference = new AtomicReference<>();
        AtomicReference<List<MediaBrowser.MediaItem>> childrenReference = new AtomicReference<>();

        Handler main = new Handler(Looper.getMainLooper());
        main.post(() -> {
            MediaBrowser browser = new MediaBrowser(
                    context,
                    new ComponentName(context, RadioService.class),
                    new MediaBrowser.ConnectionCallback() {
                        @Override public void onConnected() {
                            try {
                                MediaBrowser active = browserReference.get();
                                assertNotNull(active);
                                assertFalse(active.getRoot().isEmpty());
                                assertNotNull(new MediaController(context, active.getSessionToken()));
                                active.subscribe(active.getRoot(), new MediaBrowser.SubscriptionCallback() {
                                    @Override public void onChildrenLoaded(
                                            String parentId, List<MediaBrowser.MediaItem> children) {
                                        childrenReference.set(children);
                                        childrenLoaded.countDown();
                                    }

                                    @Override public void onError(String parentId) {
                                        failure.set(new AssertionError("Media browser rejected root: " + parentId));
                                        childrenLoaded.countDown();
                                    }
                                });
                            } catch (Throwable error) {
                                failure.set(error);
                            } finally {
                                connected.countDown();
                            }
                        }

                        @Override public void onConnectionFailed() {
                            failure.set(new AssertionError("MediaBrowser connection failed"));
                            connected.countDown();
                            childrenLoaded.countDown();
                        }

                        @Override public void onConnectionSuspended() {
                            failure.set(new AssertionError("MediaBrowser connection suspended"));
                            connected.countDown();
                            childrenLoaded.countDown();
                        }
                    },
                    null);
            browserReference.set(browser);
            browser.connect();
        });

        assertTrue("MediaBrowser did not connect", connected.await(15, TimeUnit.SECONDS));
        if (failure.get() != null) throw new AssertionError(failure.get());
        assertTrue("MediaBrowser did not return children", childrenLoaded.await(15, TimeUnit.SECONDS));
        if (failure.get() != null) throw new AssertionError(failure.get());

        List<MediaBrowser.MediaItem> children = childrenReference.get();
        assertNotNull(children);
        assertEquals(1, children.size());
        assertEquals("allthings140_live", children.get(0).getMediaId());
        assertTrue(children.get(0).isPlayable());
        assertFalse(children.get(0).isBrowsable());

        main.post(() -> {
            MediaBrowser browser = browserReference.get();
            if (browser != null) browser.disconnect();
        });
    }
}
