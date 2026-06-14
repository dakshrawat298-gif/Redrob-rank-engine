export default function JdUnderstanding() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(109,40,217,0.20),transparent_46%),radial-gradient(circle_at_90%_85%,rgba(59,130,246,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">03 / Evaluation</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          Semantic Fit <span className="text-accent">&gt;</span> Keyword Traps
        </h2>

        <div className="mt-[6vh] grid grid-cols-3 gap-[2vw] flex-1">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw] flex flex-col">
            <div className="font-mono text-[1.6vw] text-accent">384-dim</div>
            <div className="mt-[2vh] h-[0.3vh] w-full bg-white/10 rounded-full" />
            <p className="mt-[2.6vh] text-[2vw] leading-snug text-slate-100 text-pretty">
              Matches meaning via 384-dim embeddings — "retrieval" matches "search ranking".
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw] flex flex-col">
            <div className="font-mono text-[1.6vw] text-accent">regex \b</div>
            <div className="mt-[2vh] h-[0.3vh] w-full bg-white/10 rounded-full" />
            <p className="mt-[2.6vh] text-[2vw] leading-snug text-slate-100 text-pretty">
              Applies whole-word boundaries to prevent naive substring matches.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw] flex flex-col">
            <div className="font-mono text-[1.6vw] text-accent">TITLE_DENY_LIST</div>
            <div className="mt-[2vh] h-[0.3vh] w-full bg-white/10 rounded-full" />
            <p className="mt-[2.6vh] text-[2vw] leading-snug text-slate-100 text-pretty">
              Enforces a strict deny-list to drop irrelevant roles instantly.
            </p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>03 / 10</span>
        </div>
      </div>
    </div>
  );
}
