export default function Workflow() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_15%,rgba(59,130,246,0.20),transparent_46%),radial-gradient(circle_at_10%_88%,rgba(109,40,217,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">06 / Workflow</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          Offline to Runtime Pipeline
        </h2>

        <div className="mt-[5vh] flex flex-col gap-[2.2vh]">
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.4vh]">
            <span className="w-[10vw] shrink-0 font-mono text-[1.5vw] tracking-[0.2em] uppercase text-primary">Offline</span>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Stream 100k JSONL → build byte-offset index → serialize FAISS store.
            </p>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.4vh]">
            <span className="w-[10vw] shrink-0 font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent">Runtime</span>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Parse JD → embed → recall top 1,000 → lazy-load full records.
            </p>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.4vh]">
            <span className="w-[10vw] shrink-0 font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent">Runtime</span>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Execute hard filters → apply behavioral multipliers → AST reasoning.
            </p>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-accent/30 bg-gradient-to-r from-primary/12 to-accent/8 px-[2.2vw] py-[2.4vh]">
            <span className="w-[10vw] shrink-0 font-mono text-[1.5vw] tracking-[0.2em] uppercase text-text">Output</span>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Write a valid, ranked team_vibecoder.csv — reproducible byte-for-byte.
            </p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>06 / 10</span>
        </div>
      </div>
    </div>
  );
}
