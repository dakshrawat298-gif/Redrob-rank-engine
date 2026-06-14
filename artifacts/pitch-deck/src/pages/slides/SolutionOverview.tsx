export default function SolutionOverview() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_15%,rgba(59,130,246,0.20),transparent_46%),radial-gradient(circle_at_10%_90%,rgba(109,40,217,0.18),transparent_45%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">02 / Solution</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          The 4.3-Second Recruiter
        </h2>

        <div className="mt-[5vh] grid grid-cols-2 gap-[2.2vw]">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">01</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              A CPU-only, two-pass ranker processing 100k candidates.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">02</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Pass 1 (Recall): FAISS semantic search pulls top 1,000 matches.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">03</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Pass 2 (Precision): Behavioral scoring, honeypot dropping, and ranking.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">04</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Fully offline, deterministic, and zero-hallucination.
            </p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>02 / 10</span>
        </div>
      </div>
    </div>
  );
}
