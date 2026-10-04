// Kamera-Sonde: JPEG-Kodierung im Worker (Variante „Worker“ aus T4).
// Bekommt ein VideoFrame (übertragen), schneidet zu, kodiert und schickt die Bytes zurück.
self.onmessage = async (e) => {
  const { frame, job } = e.data;
  const t0 = performance.now();
  try {
    const { sx, sy, sw, sh, ow, oh, quality } = job;
    const canvas = new OffscreenCanvas(ow, oh);
    canvas.getContext("2d").drawImage(frame, sx, sy, sw, sh, 0, 0, ow, oh);
    frame.close();
    const t1 = performance.now();
    const blob = await canvas.convertToBlob({ type: "image/jpeg", quality });
    const buf = await blob.arrayBuffer();
    const t2 = performance.now();
    self.postMessage({ id: job.id, buf, zeichnenMs: t1 - t0, kodierenMs: t2 - t1 }, [buf]);
  } catch (err) {
    try { frame.close(); } catch {}
    self.postMessage({ id: job.id, fehler: String(err) });
  }
};
