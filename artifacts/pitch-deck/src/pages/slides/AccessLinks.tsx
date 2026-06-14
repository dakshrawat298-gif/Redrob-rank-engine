export default function AccessLinks() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(109,40,217,0.30),transparent_44%),radial-gradient(circle_at_85%_82%,rgba(59,130,246,0.24),transparent_46%)]" />
      <div className="absolute inset-0 opacity-[0.05] bg-[linear-gradient(rgba(255,255,255,0.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.6)_1px,transparent_1px)] bg-[size:4vw_4vw]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col justify-between">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">10 / Access</span>
        </div>

        <div>
          <h2 className="text-[5vw] font-extrabold tracking-tight leading-[1.04] text-balance">
            Ready for Stage 4 <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">Code Review</span>
          </h2>
          <p className="mt-[3vh] text-[2vw] text-slate-200 max-w-[62vw] text-pretty">
            The architecture is locked, live, and reproducible. Built solo by Daksh Rawat.
          </p>

          <div className="mt-[5vh] grid grid-cols-2 gap-[2.2vw]">
            <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
              <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-muted mb-[1.6vh]">Repository</div>
              <a
                href="https://github.com/dakshrawat298-gif/Redrob-rank-engine"
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[1.8vw] text-accent underline decoration-accent/50 underline-offset-[0.5vw] break-all"
              >
                github.com/dakshrawat298-gif/Redrob-rank-engine.git
              </a>
            </div>
            <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
              <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-muted mb-[1.6vh]">Verify</div>
              <p className="font-mono text-[1.8vw] text-text">git clone → run → reproduce</p>
              <p className="mt-[1.2vh] text-[1.6vw] text-muted">Byte-identical team_vibecoder.csv output</p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-[1.2vw]">
            <div className="h-[1.8vw] w-[1.8vw] rounded-[0.35vw] bg-gradient-to-br from-primary to-accent" />
            <span className="font-mono text-[1.7vw] font-extrabold text-text">redrob-rank-engine</span>
          </div>
          <span className="font-mono text-[1.5vw] text-muted/80">10 / 10</span>
        </div>
      </div>
    </div>
  );
}
