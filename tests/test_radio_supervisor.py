import io
import json
import unittest
from unittest import mock

from tools import radio_supervisor


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def response(payload):
    return _Response(json.dumps(payload).encode("utf-8"))


class RadioSupervisorHealthTests(unittest.TestCase):
    def test_requires_listener_facing_live_source(self):
        payload = {
            "ok": True,
            "autodj": {"running": True},
            "icecast": {"online": True, "live_source": False},
        }
        with mock.patch.object(radio_supervisor.urllib.request, "urlopen", return_value=response(payload)):
            self.assertFalse(radio_supervisor.api_ok())

    def test_accepts_attached_live_source(self):
        payload = {
            "ok": True,
            "autodj": {"running": True},
            "icecast": {"online": True, "live_source": True},
        }
        with mock.patch.object(radio_supervisor.urllib.request, "urlopen", return_value=response(payload)):
            self.assertTrue(radio_supervisor.api_ok())

    def test_listener_audio_requires_decoded_signal(self):
        completed = mock.Mock(returncode=0, stderr="[Parsed_volumedetect] max_volume: -8.4 dB\n")
        with mock.patch.object(radio_supervisor.subprocess, "run", return_value=completed):
            self.assertTrue(radio_supervisor.listener_audio_ok())

    def test_listener_audio_rejects_silence(self):
        completed = mock.Mock(returncode=0, stderr="[Parsed_volumedetect] max_volume: -inf dB\n")
        with mock.patch.object(radio_supervisor.subprocess, "run", return_value=completed):
            self.assertFalse(radio_supervisor.listener_audio_ok())


if __name__ == "__main__":
    unittest.main()
