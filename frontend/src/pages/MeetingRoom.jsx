import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Circle, Clock, Maximize2, Mic, MicOff, MonitorUp, Move, PhoneOff, SignalHigh, SignalLow, SignalMedium, User, Video, VideoOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

function useRecorder(id, local, remote, send) {
  const r = useRef(null);
  const upload = (kind) => { let idx = 0, chain = Promise.resolve(); return { push: (blob) => { const i = idx++; chain = chain.then(() => api.post(`/meetings/${id}/recording/${kind}/chunk?idx=${i}`, blob, { headers: { "Content-Type": "application/octet-stream" } }).catch(() => {})); }, flush: () => chain }; };
  const start = () => {
    const cv = document.createElement("canvas"); cv.width = 640; cv.height = 180;
    const ctx = cv.getContext("2d");
    const draw = setInterval(() => { ctx.fillStyle = "#000"; ctx.fillRect(0, 0, 640, 180); if (remote.current) ctx.drawImage(remote.current, 0, 0, 320, 180); if (local.current) ctx.drawImage(local.current, 320, 0, 320, 180); }, 100);
    const ac = new AudioContext(); const dest = ac.createMediaStreamDestination();
    [local.current?.srcObject, remote.current?.srcObject].forEach((s) => s && s.getAudioTracks().length && ac.createMediaStreamSource(s).connect(dest));
    const vs = new MediaStream([...cv.captureStream(10).getVideoTracks(), ...dest.stream.getAudioTracks()]);
    const vr = new MediaRecorder(vs, { mimeType: "video/webm", videoBitsPerSecond: 200000, audioBitsPerSecond: 32000 });
    const ar = new MediaRecorder(dest.stream, { mimeType: "audio/webm", audioBitsPerSecond: 16000 });
    const vu = upload("video"), au = upload("audio");
    vr.ondataavailable = (e) => e.data.size && vu.push(e.data);
    ar.ondataavailable = (e) => e.data.size && au.push(e.data);
    vr.start(10000); ar.start(10000);
    r.current = { vr, ar, vu, au, draw, ac };
    send("rec", { on: true });
  };
  const stop = async () => {
    const x = r.current; if (!x) return; r.current = null;
    const stopped = (rec) => new Promise((res) => { rec.onstop = res; rec.stop(); });
    await Promise.all([stopped(x.vr), stopped(x.ar)]);
    clearInterval(x.draw); x.ac.close();
    await Promise.all([x.vu.flush(), x.au.flush()]);
    await api.post(`/meetings/${id}/recording/done`).catch(() => {});
    send("rec", { on: false });
  };
  return { start, stop, active: () => !!r.current };
}

export default function MeetingRoom() {
  const { id } = useParams();
  const { t, user } = useApp();
  const nav = useNavigate();
  const staff = user.role !== "client";
  const local = useRef(null), remote = useRef(null), pc = useRef(null), since = useRef(0);
  const camStream = useRef(null), screen = useRef(null), comp = useRef(null);
  const [state, setState] = useState("init");
  const [rec, setRec] = useState(false), [peerRec, setPeerRec] = useState(false);
  const [sharing, setSharing] = useState(false), [peerShare, setPeerShare] = useState(false);
  const [camOff, setCamOff] = useState(false), [micOff, setMicOff] = useState(false);
  const [peerCamOff, setPeerCamOff] = useState(false), [peerMicOff, setPeerMicOff] = useState(false);
  const [info, setInfo] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [quality, setQuality] = useState("");
  const [pip, setPip] = useState({ pos: "tr", size: "sm" });
  const pipRef = useRef(pip); pipRef.current = pip;
  const corner = { tr: "top-3 right-3", tl: "top-3 left-3", br: "bottom-16 right-3", bl: "bottom-16 left-3" };
  const sizeW = { sm: "w-28 md:w-44", lg: "w-40 md:w-64" };
  const pipCls = `absolute z-10 ${corner[pip.pos]} ${sizeW[pip.size]} aspect-video overflow-hidden rounded-lg border-2 border-white/70 bg-slate-900 shadow-lg`;
  const cyclePos = () => setPip((p) => ({ ...p, pos: { tr: "br", br: "bl", bl: "tl", tl: "tr" }[p.pos] }));
  const connTs = useRef(0);
  const otherName = info ? (staff ? info.client_name : info.consultant_name) : "";
  const fmtDur = (s) => [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map((n) => String(n).padStart(2, "0")).join(":");
  const send = (type, data = {}) => api.post(`/meetings/${id}/signal`, { type, data }).catch(() => {});
  const recorder = useRecorder(id, local, remote, send);

  useEffect(() => {
    let alive = true, timer, pending = [];
    (async () => {
      const { data: ice } = await api.get("/meetings/ice");
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360, frameRate: 15 }, audio: true });
      if (!alive) return stream.getTracks().forEach((tr) => tr.stop());
      camStream.current = stream;
      stream.getAudioTracks().forEach((tr) => (tr.enabled = false));
      setMicOff(true);
      local.current.srcObject = stream;
      const p = new RTCPeerConnection(ice); pc.current = p;
      stream.getTracks().forEach((tr) => p.addTrack(tr, stream));
      p.ontrack = (e) => { remote.current.srcObject = e.streams[0]; setState("connected"); };
      p.onicecandidate = (e) => e.candidate && send("ice", e.candidate.toJSON());
      p.onconnectionstatechange = () => ["disconnected", "failed"].includes(p.connectionState) && setState("waiting");
      const remoteDesc = async (d) => { await p.setRemoteDescription(d); for (const c of pending) await p.addIceCandidate(c).catch(() => {}); pending = []; };
      const handle = async (m) => {
        if (m.type === "hello" && staff) { const o = await p.createOffer({ iceRestart: true }); await p.setLocalDescription(o); send("offer", { type: o.type, sdp: o.sdp }); }
        if (m.type === "hello") toast.info(t("mt_peer_joined"));
        if (m.type === "offer" && !staff) { await remoteDesc(m.data); const a = await p.createAnswer(); await p.setLocalDescription(a); send("answer", { type: a.type, sdp: a.sdp }); }
        if (m.type === "answer" && staff) await remoteDesc(m.data);
        if (m.type === "ice") { if (p.remoteDescription) await p.addIceCandidate(m.data).catch(() => {}); else pending.push(m.data); }
        if (m.type === "rec") setPeerRec(!!m.data.on);
        if (m.type === "share") setPeerShare(!!m.data.on);
        if (m.type === "cam") { const off = !m.data.on; setPeerCamOff(off); toast.info(t(off ? "mt_peer_cam_off" : "mt_peer_cam_on")); }
        if (m.type === "mic") setPeerMicOff(!m.data.on);
        if (m.type === "leave") { toast.info(t("mt_peer_left")); setPeerShare(false); setState("ended"); if (staff) api.post(`/meetings/${id}/end`).catch(() => {}); if (recorder.active()) await recorder.stop(); nav("/consulting"); return; }
        if (m.type === "bye") { setState("waiting"); setPeerShare(false); setPeerCamOff(false); toast.info(t("mt_peer_bye")); }
      };
      await send("hello");
      setState("waiting");
      const poll = async () => {
        if (!alive) return;
        try {
          const { data } = await api.get(`/meetings/${id}/signal?since=${since.current}`);
          for (const m of data) { since.current = Math.max(since.current, m.at); await handle(m).catch(() => {}); }
        } catch { /* retry */ }
        timer = setTimeout(poll, 1000);
      };
      poll();
    })().catch((e) => { setState("nomedia"); toast.error(errMsg(e)); });
    return () => { alive = false; clearTimeout(timer); send("bye"); pc.current?.close(); if (comp.current) { cancelAnimationFrame(comp.current.raf); comp.current.out.getTracks().forEach((tr) => tr.stop()); } [screen.current, camStream.current, local.current?.srcObject].forEach((s) => s && s.getTracks && s.getTracks().forEach((tr) => tr.stop())); };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const vSender = () => pc.current?.getSenders().find((s) => s.track && s.track.kind === "video");
  const stopComposite = () => {
    if (!comp.current) return;
    cancelAnimationFrame(comp.current.raf);
    comp.current.screenV.srcObject = null;
    comp.current.camV.srcObject = null;
    comp.current.out.getTracks().forEach((tr) => tr.stop());
    comp.current = null;
  };
  const stopShare = async () => {
    stopComposite();
    const camTrack = camOff ? null : camStream.current?.getVideoTracks()[0];
    const s = vSender();
    if (s) await s.replaceTrack(camTrack || null);
    local.current.srcObject = camOff ? null : (camStream.current || null);
    screen.current?.getTracks().forEach((tr) => tr.stop());
    screen.current = null;
    setSharing(false);
    send("share", { on: false });
  };
  const shareScreen = async () => {
    if (sharing) return stopShare();
    try {
      const ds = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: false });
      screen.current = ds;
      const screenV = document.createElement("video"); screenV.srcObject = ds; screenV.muted = true; await screenV.play();
      const camV = document.createElement("video"); camV.muted = true;
      const camTracks = !camOff && camStream.current ? camStream.current.getVideoTracks() : [];
      if (camTracks.length) { camV.srcObject = new MediaStream(camTracks); await camV.play().catch(() => {}); }
      const canvas = document.createElement("canvas"); canvas.width = 1280; canvas.height = 720;
      const ctx = canvas.getContext("2d");
      const draw = () => {
        ctx.fillStyle = "#071A2B"; ctx.fillRect(0, 0, canvas.width, canvas.height);
        if (screenV.videoWidth) {
          const r = Math.min(canvas.width / screenV.videoWidth, canvas.height / screenV.videoHeight);
          const w = screenV.videoWidth * r, h = screenV.videoHeight * r;
          ctx.drawImage(screenV, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
        }
        if (camV.videoWidth) {
          const cfg = pipRef.current;
          const pw = cfg.size === "lg" ? 380 : 260, ph = Math.round(pw * 9 / 16), m = 20;
          const x = cfg.pos[1] === "r" ? canvas.width - pw - m : m;
          const y = cfg.pos[0] === "t" ? m : canvas.height - ph - m;
          ctx.drawImage(camV, x, y, pw, ph);
          ctx.strokeStyle = "#00A878"; ctx.lineWidth = 3; ctx.strokeRect(x, y, pw, ph);
        }
        comp.current.raf = requestAnimationFrame(draw);
      };
      const out = canvas.captureStream(15);
      comp.current = { screenV, camV, out, raf: 0 };
      draw();
      const s = vSender(); if (s) await s.replaceTrack(out.getVideoTracks()[0]);
      local.current.srcObject = ds;
      setSharing(true);
      send("share", { on: true });
      ds.getVideoTracks()[0].onended = () => stopShare();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const toggleRec = async () => { if (rec) { setRec(false); await recorder.stop(); toast.success(t("mt_rec_saved")); } else { recorder.start(); setRec(true); } };
  const toggleCam = async () => {
    if (!camOff) {
      camStream.current?.getVideoTracks().forEach((tr) => tr.stop());
      if (!sharing) { const s = vSender(); if (s) await s.replaceTrack(null); if (local.current) local.current.srcObject = null; }
      setCamOff(true); send("cam", { on: false });
    } else {
      try {
        const ns = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360, frameRate: 15 } });
        const vtrack = ns.getVideoTracks()[0];
        const merged = new MediaStream([vtrack, ...(camStream.current?.getAudioTracks() || [])]);
        camStream.current = merged;
        if (!sharing) { const s = vSender(); if (s) await s.replaceTrack(vtrack); if (local.current) local.current.srcObject = merged; }
        setCamOff(false); send("cam", { on: true });
      } catch (e) { toast.error(errMsg(e)); }
    }
  };
  const toggleMic = () => {
    const a = camStream.current?.getAudioTracks()[0];
    if (!a) return;
    const willOff = !micOff;
    a.enabled = !willOff;
    setMicOff(willOff);
    send("mic", { on: !willOff });
  };
  const leave = async () => { if (sharing) await stopShare(); await send("leave"); if (recorder.active()) await recorder.stop(); if (staff) await api.post(`/meetings/${id}/end`).catch(() => {}); [screen.current, camStream.current, local.current?.srcObject].forEach((s) => s && s.getTracks && s.getTracks().forEach((tr) => tr.stop())); nav("/consulting"); };

  useEffect(() => { api.get(`/meetings/${id}`).then((r) => setInfo(r.data)).catch(() => {}); }, [id]);
  useEffect(() => {
    const iv = setInterval(() => {
      if (state === "connected") {
        if (!connTs.current) connTs.current = Date.now();
        setElapsed(Math.floor((Date.now() - connTs.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(iv);
  }, [state]);
  useEffect(() => {
    if (state !== "connected") { setQuality(""); return; }
    let alive = true;
    const iv = setInterval(async () => {
      const p = pc.current; if (!p) return;
      try {
        const stats = await p.getStats();
        let rtt = null, loss = 0, recv = 0;
        stats.forEach((r) => {
          if (r.type === "candidate-pair" && r.nominated && r.currentRoundTripTime != null) rtt = r.currentRoundTripTime;
          if (r.type === "inbound-rtp" && r.kind === "video") { loss += r.packetsLost || 0; recv += r.packetsReceived || 0; }
        });
        const lr = recv ? loss / (recv + loss) : 0;
        let q = "good";
        if ((rtt != null && rtt > 0.4) || lr > 0.05) q = "poor";
        else if ((rtt != null && rtt > 0.2) || lr > 0.02) q = "fair";
        if (alive) setQuality(q);
      } catch { /* ignore */ }
    }, 3000);
    return () => { alive = false; clearInterval(iv); };
  }, [state]);

  return (
    <div className="flex h-[calc(100dvh-8rem)] min-h-0 flex-col gap-2 overflow-hidden" data-testid="meeting-room">
      <div className="flex items-center gap-2 overflow-x-auto flex-nowrap md:flex-wrap [&>*]:shrink-0 no-scrollbar">
        <h1 className="font-display text-lg md:text-2xl font-extrabold text-[#071A2B]">{t("mt_room")}</h1>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600" data-testid="meeting-state">{t(`mt_state_${state}`)}</span>
        {(rec || peerRec) && <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-600" data-testid="meeting-rec-badge"><Circle className="h-3 w-3 fill-red-600" />{t("mt_recording")}</span>}
        {sharing && <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-[#00A878]" data-testid="meeting-share-badge"><MonitorUp className="h-3 w-3" />{t("mt_sharing")}</span>}
        {peerShare && <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-[#00A878]" data-testid="meeting-peer-share-badge"><MonitorUp className="h-3 w-3" />{t("mt_peer_sharing")}</span>}
        {state === "connected" && <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 font-num text-xs text-slate-700" data-testid="meeting-duration"><Clock className="h-3 w-3" />{t("mt_conn_time")} {fmtDur(elapsed)}</span>}
        {quality && <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${quality === "good" ? "bg-emerald-50 text-[#00A878]" : quality === "fair" ? "bg-amber-50 text-amber-600" : "bg-red-50 text-red-600"}`} data-testid="meeting-quality">{quality === "good" ? <SignalHigh className="h-3 w-3" /> : quality === "fair" ? <SignalMedium className="h-3 w-3" /> : <SignalLow className="h-3 w-3" />}{t(`mt_quality_${quality}`)}</span>}
        {micOff && <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-600" data-testid="meeting-mic-badge"><MicOff className="h-3 w-3" />{t("mt_mic_is_off")}</span>}
        {peerMicOff && <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600" data-testid="meeting-peer-mic-badge"><MicOff className="h-3 w-3" />{t("mt_peer_mic_off")}</span>}
        {peerCamOff && <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600" data-testid="meeting-peer-cam-badge"><VideoOff className="h-3 w-3" />{t("mt_peer_cam_off")}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600" data-testid="meeting-participants">
        <User className="h-3.5 w-3.5 text-[#00A878]" />
        <span className="font-semibold text-[#071A2B]">{otherName || "—"}</span>
        <span className="text-slate-400">·</span>
        <span>{user.name}（{t("mt_you")}）</span>
      </div>
      <div className="relative mx-auto w-full min-h-[46vh] md:min-h-0 flex-1 overflow-hidden rounded-2xl bg-[#071A2B] shadow-xl" data-testid="meeting-stage">
        <div className={sharing ? pipCls : "absolute inset-0"} data-testid="meeting-remote-wrap">
          <video ref={remote} autoPlay playsInline className={`h-full w-full ${sharing ? "object-cover" : "object-contain"} bg-[#071A2B]`} data-testid="meeting-remote-video" />
          <span className="absolute bottom-1 left-1 rounded bg-black/55 px-1.5 py-0.5 text-[11px] font-semibold text-white" data-testid="meeting-remote-name">{otherName || "—"}</span>
          {peerCamOff && !peerShare && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#071A2B] text-slate-300" data-testid="meeting-peer-cam-off-overlay"><VideoOff className="h-7 w-7" /><span className="text-xs font-semibold">{otherName || "—"} · {t("mt_cam_is_off")}</span></div>}
        </div>
        <div className={sharing ? "absolute inset-0" : pipCls} data-testid="meeting-local-wrap">
          <video ref={local} autoPlay playsInline muted className={`h-full w-full ${sharing ? "object-contain" : "object-cover"} bg-slate-900`} data-testid="meeting-local-video" />
          <span className="absolute bottom-1 left-1 rounded bg-black/55 px-1.5 py-0.5 text-[11px] font-semibold text-white" data-testid="meeting-local-name">{sharing ? t("mt_sharing") : `${user.name}（${t("mt_you")}）`}</span>
          {camOff && !sharing && <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-slate-900 text-slate-300" data-testid="meeting-cam-off-overlay"><VideoOff className="h-6 w-6" /><span className="text-[11px] font-semibold">{t("mt_cam_is_off")}</span></div>}
        </div>
        <div className="absolute inset-x-0 bottom-3 z-20 flex flex-nowrap justify-center gap-1.5 px-2 md:flex-wrap md:gap-2" data-testid="meeting-controls">
          <Button variant="outline" size="sm" className={camOff ? "text-slate-500" : ""} disabled={["init", "nomedia"].includes(state)} onClick={toggleCam} data-testid="meeting-cam-btn">{camOff ? <VideoOff className="h-4 w-4 md:mr-1" /> : <Video className="h-4 w-4 md:mr-1" />}<span className="hidden md:inline">{t(camOff ? "mt_cam_on" : "mt_cam_off")}</span></Button>
          <Button variant="outline" size="sm" className={micOff ? "text-red-600" : ""} disabled={["init", "nomedia"].includes(state)} onClick={toggleMic} data-testid="meeting-mic-btn">{micOff ? <MicOff className="h-4 w-4 md:mr-1" /> : <Mic className="h-4 w-4 md:mr-1" />}<span className="hidden md:inline">{t(micOff ? "mt_mic_on" : "mt_mic_off")}</span></Button>
          <Button variant="outline" size="sm" className={sharing ? "text-[#00A878]" : ""} disabled={state !== "connected" && !sharing} onClick={shareScreen} data-testid="meeting-share-btn"><MonitorUp className="h-4 w-4 md:mr-1" /><span className="hidden md:inline">{t(sharing ? "mt_share_stop" : "mt_share_start")}</span></Button>
          {staff && <Button variant="outline" size="sm" className={rec ? "text-red-600" : ""} disabled={state !== "connected" && !rec} onClick={toggleRec} data-testid="meeting-rec-btn"><Circle className={`h-4 w-4 md:mr-1 ${rec ? "fill-red-600" : ""}`} /><span className="hidden md:inline">{t(rec ? "mt_rec_stop" : "mt_rec_start")}</span></Button>}
          <Button variant="outline" size="sm" onClick={cyclePos} title={t("mt_pip_move")} data-testid="meeting-pip-move-btn"><Move className="h-4 w-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => setPip((p) => ({ ...p, size: p.size === "sm" ? "lg" : "sm" }))} title={t("mt_pip_size")} data-testid="meeting-pip-size-btn"><Maximize2 className="h-4 w-4" /></Button>
          <Button size="sm" className="bg-red-600 text-white hover:bg-red-700" onClick={leave} data-testid="meeting-leave-btn"><PhoneOff className="h-4 w-4 md:mr-1" /><span className="hidden md:inline">{t("mt_leave")}</span></Button>
        </div>
      </div>
      <p className="hidden md:block text-xs text-slate-500">{t("mt_note")}</p>
    </div>
  );
}
