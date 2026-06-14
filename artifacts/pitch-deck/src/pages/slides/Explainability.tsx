export default function Explainability() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_18%,rgba(109,40,217,0.20),transparent_46%),radial-gradient(circle_at_88%_86%,rgba(59,130,246,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">05 / Explainability</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          100% Grounded Reasoning
        </h2>

        <div className="mt-[5vh] grid grid-cols-2 gap-[2.2vw]">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">01</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Every score is traceable — no black-box neural ranking.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">02</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Reasons are extracted from real resume text via AST parsing.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">03</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Strict anti-hallucination: if text is absent, the claim is dropped.
            </p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.2vw]">
            <div className="font-mono text-[1.7vw] text-accent mb-[1.6vh]">04</div>
            <p className="text-[2vw] leading-snug text-slate-100 text-pretty">
              Output maps each candidate to a transparent score breakdown.
            </p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>05 / 10</span>
        </div>
      </div>
    </div>
  );
}
