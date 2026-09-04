"""Outbound-only worker for the private Wardrobe Site. No public listener."""
import argparse
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv
from PIL import Image, ImageOps

from .ai.stylewell4b import StyleWell4BAnalyzer
from .config import Settings

log = logging.getLogger('wardrobe.site_worker')
MAX_PHOTO_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000


class Worker:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / '.env.site-worker')
        self.origin = os.environ.get('WARDROBE_SITE_URL', '').rstrip('/')
        self.secret = os.environ.get('WARDROBE_WORKER_SECRET', '')
        self.gate = os.environ.get('WARDROBE_SITE_GATE_TOKEN', '')
        if not self.origin.startswith('https://') or not self.secret or not self.gate:
            raise RuntimeError('The protected Site worker connection has not been configured.')
        settings = Settings()
        self.analyzer = StyleWell4BAnalyzer(settings.model_id, settings.model_revision, settings.device)

    def request(self, path, payload=None, lease=None, image=False):
        headers = {'X-Wardrobe-Worker': self.secret, 'OAI-Sites-Authorization': 'Bearer ' + self.gate}
        if lease:
            headers['X-Wardrobe-Lease'] = lease
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.origin + '/api/worker/' + path,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        # A redirected service request must never forward credentials to another origin.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(request, timeout=30) as response:
            limit = MAX_PHOTO_BYTES if image else 65536
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Response exceeded the permitted size.')
            return data if image else json.loads(data)

    def process(self, job):
        finished = threading.Event()
        def heartbeat():
            started = time.monotonic()
            while not finished.wait(30):
                if time.monotonic() - started > 600:
                    log.warning('Recognition exceeded its lease budget.')
                    return
                try:
                    self.request(job['id'] + '/heartbeat', {}, job['lease'])
                except Exception:
                    log.warning('Could not renew the recognition lease.')
                    return
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            # This directory is exclusively owned by this job and is always cleaned up.
            with tempfile.TemporaryDirectory(prefix='wardrobe-site-job-') as temporary:
                source = Path(temporary) / 'source.bin'
                prepared = Path(temporary) / 'analysis.jpg'
                source.write_bytes(self.request(job['id'] + '/photo', lease=job['lease'], image=True))
                with Image.open(source) as raw:
                    if raw.format not in {'JPEG', 'PNG', 'WEBP'} or raw.width * raw.height > 24_000_000:
                        raise ValueError('Unsupported or oversized image.')
                    image = ImageOps.exif_transpose(raw).convert('RGB')
                    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                    image.save(prepared, 'JPEG', quality=92)
                analysis = self.analyzer.analyze(prepared, job['itemId'])
                if not analysis.parseSuccess:
                    raise ValueError('Recognition could not be interpreted.')
                result = analysis.model_dump(include={'category', 'type', 'color', 'pattern', 'fabric', 'fit', 'style', 'occasion', 'season', 'inferenceTimeMs'})
                self.request(job['id'] + '/complete', {'result': result}, job['lease'])
                log.info('Clothing recognition completed; temporary files removed on exit.')
        except Exception as error:
            # Do not log image contents, user identity, model text, URLs with secrets, or tokens.
            log.warning('Recognition failed (%s). The app can retry.', type(error).__name__)
            try:
                self.request(job['id'] + '/complete', {'error': True}, job['lease'])
            except Exception:
                log.warning('Could not report completion; the lease will expire safely.')
        finally:
            finished.set()
            thread.join(timeout=2)

    def run(self, once=False):
        log.info('Connecting to the protected Wardrobe Site. The AI model stays on this PC.')
        while True:
            try:
                result = self.request('claim', {})
                if result.get('job'):
                    log.info('Processing one queued clothing photo.')
                    self.process(result['job'])
                elif once:
                    log.info('Connection verified. No photo is queued.')
                if once:
                    return
                if not result.get('job'):
                    time.sleep(15)
            except (urllib.error.URLError, ValueError) as error:
                log.warning('Site connection unavailable (%s). Retrying shortly.', type(error).__name__)
                if once:
                    raise SystemExit(1)
                time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Check the connection and process at most one job.')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    lock_path = Path(__file__).resolve().parents[1] / '.site-worker.lock'
    with lock_path.open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SystemExit('A Wardrobe Site worker is already running on this PC.')
        try:
            Worker().run(once=args.once)
        except KeyboardInterrupt:
            log.info('Worker stopped. The website will keep queued photos for later.')


if __name__ == '__main__':
    main()
