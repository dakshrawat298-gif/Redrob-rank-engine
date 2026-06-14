export default function RankingMethodology() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_88%_18%,rgba(59,130,246,0.20),transparent_46%),radial-gradient(circle_at_8%_88%,rgba(109,40,217,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">04 / Methodology</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          Math, Not Magic
        </h2>

        <div className="mt-[4.5vh] rounded-[1vw] border border-accent/30 bg-gradient-to-r from-primary/15 to-accent/10 p-[2.4vw]">
          <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-muted mb-[1.4vh]">scoring formula</div>
          <p className="font-mono text-[2.5vw] font-semibold leading-tight text-text text-pretty">
            Final Score = <span className="text-accent">Semantic Base</span> × <span className="text-primary">Behavioral Multipliers</span>
          </p>
        </div>

        <div className="mt-[4vh] grid grid-cols-3 gap-[2vw]">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2vw]">
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Embed JD → IndexFlatIP cosine similarity → Base Score.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2vw]">
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Job-hopper penalty (0.85×) from actual career tenure.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2vw]">
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Deterministic tie-breaking: Score → Semantic → Candidate_ID.
            </p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>04 / 10</span>
        </div>
      </div>
    </div>
  );
}
