export default function Title() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_18%,rgba(109,40,217,0.32),transparent_44%),radial-gradient(circle_at_88%_84%,rgba(59,130,246,0.24),transparent_46%)]" />
      <div className="absolute inset-0 opacity-[0.05] bg-[linear-gradient(rgba(255,255,255,0.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.6)_1px,transparent_1px)] bg-[size:4vw_4vw]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col justify-between">
        <div className="flex items-center gap-[1.2vw]">
          <div className="h-[1.8vw] w-[1.8vw] rounded-[0.35vw] bg-gradient-to-br from-primary to-accent" />
          <span className="font-mono text-[1.5vw] tracking-[0.34em] uppercase text-muted">Redrob · India.Runs Hackathon</span>
        </div>

        <div className="grid grid-cols-[1.45fr_1fr] gap-[4vw] items-center">
          <div>
            <h1 className="font-mono font-extrabold text-[6.2vw] leading-[1.0] tracking-tight">
              redrob-<span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">rank</span>-engine
            </h1>
            <p className="mt-[3.2vh] text-[2.2vw] font-semibold text-slate-200 text-pretty">
              Intelligent Candidate Discovery &amp; Ranking
            </p>
            <div className="mt-[3vh] flex items-center gap-[1.5vw]">
              <span className="px-[1.5vw] py-[0.9vh] rounded-full text-[1.5vw] font-semibold border border-accent/70 text-accent">
                Track 1
              </span>
            </div>
            <div className="mt-[3vh] flex flex-col gap-[1.2vh]">
              <div className="flex items-baseline gap-[0.8vw]">
                <span className="font-mono text-[1.5vw] text-muted">Team Name:</span>
                <span className="text-[1.9vw] font-semibold text-text">team_vibecoder</span>
              </div>
              <div className="flex items-baseline gap-[0.8vw]">
                <span className="font-mono text-[1.5vw] text-muted">Team Leader Name:</span>
                <span className="text-[1.9vw] text-slate-200">Daksh Rawat — Solo Founder, Architect &amp; Engineer</span>
              </div>
            </div>
          </div>

          <div className="rounded-[1vw] border border-white/10 bg-panel/80 p-[1.9vw]">
            <div className="flex items-center gap-[0.7vw] mb-[2.4vh]">
              <span className="h-[1vw] w-[1vw] rounded-full bg-[#ef4444]/80" />
              <span className="h-[1vw] w-[1vw] rounded-full bg-[#f59e0b]/80" />
              <span className="h-[1vw] w-[1vw] rounded-full bg-[#22c55e]/80" />
              <span className="ml-[0.9vw] font-mono text-[1.5vw] text-muted">rank --status</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/5 py-[1.4vh] font-mono text-[1.6vw]">
              <span className="text-muted">compute</span>
              <span className="text-text">CPU-only</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/5 py-[1.4vh] font-mono text-[1.6vw]">
              <span className="text-muted">candidates</span>
              <span className="text-accent">100k → 100</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/5 py-[1.4vh] font-mono text-[1.6vw]">
              <span className="text-muted">wall-clock</span>
              <span className="text-accent">~4.3s</span>
            </div>
            <div className="flex items-center justify-between py-[1.4vh] font-mono text-[1.6vw]">
              <span className="text-muted">network</span>
              <span className="text-text">0 calls</span>
            </div>
          </div>
        </div>

        <p className="text-[1.8vw] text-muted max-w-[58vw] text-pretty">
          Built, coded, and deployed single-handedly from a Jio Cloud PC.{" "}
          <span className="text-text font-semibold">Grit &gt; Resources.</span>
        </p>
      </div>
    </div>
  );
}
