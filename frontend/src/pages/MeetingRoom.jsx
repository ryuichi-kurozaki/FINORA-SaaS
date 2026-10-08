import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Circle, MonitorUp, PhoneOff, Video, VideoOff } from "lucide-react";
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
  const camStream = useRef(null), screen = useRef(null);
  const [state, setState] = useState("init");
  const [rec, setRec] = useState(false), [peerRec, setPeerRec] = useState(false);
  const [sharing, setSharing] = useState(false), [peerShare, setPeerShare] = useState(false);
  const [camOff, setCamOff] = useState(false);
  const send = (type, data = {}) => api.post(`/meetings/${id}/signal`, { type, data }).catch(() => {});
  const recorder = useRecorder(id, local, remote, send);

  useEffect(() => {
    let alive = true, timer, pending = [];
    (async () => {
      const { data: ice } = await api.get("/meetings/ice");
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360, frameRate: 15 }, audio: true });
      if (!alive) return stream.getTracks().forEach((tr) => tr.stop());
      camStream.current = stream;
      local.current.srcObject = stream;
      const p = new RTCPeerConnection(ice); pc.current = p;
      stream.getTracks().forEach((tr) => p.addTrack(tr, stream));
      p.ontrack = (e) => { remote.current.srcObject = e.streams[0]; setState("connected"); };
      p.onicecandidate = (e) => e.candidate && send("ice", e.candidate.toJSON());
      p.onconnectionstatechange = () => ["disconnected", "failed"].includes(p.connectionState) && setState("waiting");
      const remoteDesc = async (d) => { await p.setRemoteDescription(d); for (const c of pending) await p.addIceCandidate(c).catch(() => {}); pending = []; };
      const handle = async (m) => {
        if (m.type === "hello" && staff) { const o = await p.createOffer({ iceRestart: true }); await p.setLocalDescription(o); send("offer", { type: o.type, sdp: o.sdp }); }
        if (m.type === "offer" && !staff) { await remoteDesc(m.data); const a = await p.createAnswer(); await p.setLocalDescription(a); send("answer", { type: a.type, sdp: a.sdp }); }
        if (m.type === "answer" && staff) await remoteDesc(m.data);
        if (m.type === "ice") { if (p.remoteDescription) await p.addIceCandidate(m.data).catch(() => {}); else pending.push(m.data); }
        if (m.type === "rec") setPeerRec(!!m.data.on);
        if (m.type === "share") setPeerShare(!!m.data.on);
        if (m.type === "leave") { toast.info(t("mt_peer_left")); setPeerShare(false); setState("ended"); if (staff) api.post(`/meetings/${id}/end`).catch(() => {}); if (recorder.active()) await recorder.stop(); nav("/consulting"); return; }
        if (m.type === "bye") { setState("waiting"); setPeerShare(false); }
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
    return () => { alive = false; clearTimeout(timer); send("bye"); pc.current?.close(); screen.current?.getTracks().forEach((tr) => tr.stop()); local.current?.srcObject?.getTracks().forEach((tr) => tr.stop()); };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const vSender = () => pc.current?.getSenders().find((s) => s.track && s.track.kind === "video");
  const stopShare = async () => {
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
      const ds = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const track = ds.getVideoTracks()[0];
      const s = vSender();
      if (s) await s.replaceTrack(track);
      screen.current = ds;
      local.current.srcObject = ds;
      setSharing(true);
      send("share", { on: true });
      track.onended = () => stopShare();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const toggleRec = async () => { if (rec) { setRec(false); await recorder.stop(); toast.success(t("mt_rec_saved")); } else { recorder.start(); setRec(true); } };
  const toggleCam = async () => {
    if (!camOff) {
      camStream.current?.getVideoTracks().forEach((tr) => tr.stop());
      if (!sharing) { const s = vSender(); if (s) await s.replaceTrack(null); if (local.current) local.current.srcObject = null; }
      setCamOff(true);
    } else {
      try {
        const ns = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360, frameRate: 15 } });
        const vtrack = ns.getVideoTracks()[0];
        const merged = new MediaStream([vtrack, ...(camStream.current?.getAudioTracks() || [])]);
        camStream.current = merged;
        if (!sharing) { const s = vSender(); if (s) await s.replaceTrack(vtrack); if (local.current) local.current.srcObject = merged; }
        setCamOff(false);
      } catch (e) { toast.error(errMsg(e)); }
    }
  };
  const leave = async () => { if (sharing) await stopShare(); await send("leave"); if (recorder.active()) await recorder.stop(); if (staff) await api.post(`/meetings/${id}/end`).catch(() => {}); nav("/consulting"); };

  return (
    <div className="space-y-4" data-testid="meeting-room">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-2xl font-extrabold text-[#071A2B]">{t("mt_room")}</h1>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600" data-testid="meeting-state">{t(`mt_state_${state}`)}</span>
        {(rec || peerRec) && <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-600" data-testid="meeting-rec-badge"><Circle className="h-3 w-3 fill-red-600" />{t("mt_recording")}</span>}
        {sharing && <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-[#00A878]" data-testid="meeting-share-badge"><MonitorUp className="h-3 w-3" />{t("mt_sharing")}</span>}
        {peerShare && <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-[#00A878]" data-testid="meeting-peer-share-badge"><MonitorUp className="h-3 w-3" />{t("mt_peer_sharing")}</span>}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <video ref={remote} autoPlay playsInline className="aspect-video w-full rounded-xl bg-[#071A2B]" data-testid="meeting-remote-video" />
        <div className="relative">
          <video ref={local} autoPlay playsInline muted className="aspect-video w-full rounded-xl bg-slate-800" data-testid="meeting-local-video" />
          {camOff && !sharing && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl bg-slate-800 text-slate-300" data-testid="meeting-cam-off-overlay"><VideoOff className="h-8 w-8" /><span className="text-xs font-semibold">{t("mt_cam_is_off")}</span></div>}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {staff && <Button variant="outline" className={rec ? "text-red-600" : ""} disabled={state !== "connected" && !rec} onClick={toggleRec} data-testid="meeting-rec-btn">{t(rec ? "mt_rec_stop" : "mt_rec_start")}</Button>}
        <Button variant="outline" className={camOff ? "text-slate-500" : ""} disabled={["init", "nomedia"].includes(state)} onClick={toggleCam} data-testid="meeting-cam-btn">{camOff ? <VideoOff className="mr-1 h-4 w-4" /> : <Video className="mr-1 h-4 w-4" />}{t(camOff ? "mt_cam_on" : "mt_cam_off")}</Button>
        <Button variant="outline" className={sharing ? "text-[#00A878]" : ""} disabled={state !== "connected" && !sharing} onClick={shareScreen} data-testid="meeting-share-btn"><MonitorUp className="mr-1 h-4 w-4" />{t(sharing ? "mt_share_stop" : "mt_share_start")}</Button>
        <Button className="bg-red-600 text-white hover:bg-red-700" onClick={leave} data-testid="meeting-leave-btn"><PhoneOff className="mr-1 h-4 w-4" />{t("mt_leave")}</Button>
      </div>
      <p className="text-xs text-slate-500">{t("mt_note")}</p>
    </div>
  );
}
