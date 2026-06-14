export default function Benchmarking() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_14%,rgba(59,130,246,0.22),transparent_46%),radial-gradient(circle_at_10%_88%,rgba(109,40,217,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">08 / Benchmarks</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          Beating the Sandbox
        </h2>

        <div className="mt-[5vh] grid grid-cols-2 gap-[2.2vw]">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.4vw]">
            <div className="font-mono text-[6vw] font-extrabold leading-none text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">~4.3s</div>
            <p className="mt-[2vh] text-[2vw] text-slate-200">Wall-clock runtime</p>
            <p className="text-[1.55vw] text-muted">vs. a 300-second budget</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.4vw]">
            <div className="font-mono text-[6vw] font-extrabold leading-none text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">~0.4 GB</div>
            <p className="mt-[2vh] text-[2vw] text-slate-200">Peak RAM usage</p>
            <p className="text-[1.55vw] text-muted">against a 16 GB ceiling</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.4vw]">
            <div className="font-mono text-[4.6vw] font-extrabold leading-none text-text">1.0 → 0.537</div>
            <p className="mt-[2vh] text-[2vw] text-slate-200">Monotonic score curve</p>
            <p className="text-[1.55vw] text-muted">clean, well-distributed ranking</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.4vw]">
            <div className="font-mono text-[6vw] font-extrabold leading-none text-text">0</div>
            <p className="mt-[2vh] text-[2vw] text-slate-200">GPU &amp; network calls</p>
            <p className="text-[1.55vw] text-muted">fully offline, deterministic</p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>08 / 10</span>
        </div>
      </div>
    </div>
  );
}
