import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import java.io.FileDescriptor;
import java.io.FileOutputStream;

/** Writes everything Android plays as raw 48 kHz stereo s16le to stdout; run as root via app_process. */
public final class AudioTap {
    public static void main(String[] args) throws Exception {
        int rate = 48000;
        int channels = AudioFormat.CHANNEL_IN_STEREO;
        int encoding = AudioFormat.ENCODING_PCM_16BIT;
        int min = AudioRecord.getMinBufferSize(rate, channels, encoding);
        // Root holds CAPTURE_AUDIO_OUTPUT, which REMOTE_SUBMIX needs; recording it also mutes the (silent) primary output.
        AudioRecord rec = new AudioRecord(MediaRecorder.AudioSource.REMOTE_SUBMIX, rate, channels, encoding, Math.max(min, rate));
        if (rec.getState() != AudioRecord.STATE_INITIALIZED) {
            System.err.println("audiotap: cannot open the output capture");
            System.exit(1);
        }
        rec.startRecording();
        FileOutputStream out = new FileOutputStream(FileDescriptor.out);
        byte[] buf = new byte[rate / 100 * 4];
        while (true) {
            int n = rec.read(buf, 0, buf.length);
            if (n < 0) {
                System.err.println("audiotap: read failed " + n);
                System.exit(1);
            }
            out.write(buf, 0, n);
        }
    }
}
