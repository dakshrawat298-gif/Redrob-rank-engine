export default function SystemArchitecture() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_16%,rgba(109,40,217,0.20),transparent_46%),radial-gradient(circle_at_90%_88%,rgba(59,130,246,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">07 / Architecture</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          Enterprise Pipeline
        </h2>

        <div className="mt-[5vh] flex flex-col gap-[2.2vh]">
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.6vh]">
            <span className="w-[6vw] shrink-0 font-mono text-[2vw] font-extrabold text-primary">L1</span>
            <div>
              <p className="text-[2vw] font-semibold text-text">Embedding Layer</p>
              <p className="text-[1.7vw] text-muted">fastembed + ONNX Runtime (CPU)</p>
            </div>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.6vh]">
            <span className="w-[6vw] shrink-0 font-mono text-[2vw] font-extrabold text-accent">L2</span>
            <div>
              <p className="text-[2vw] font-semibold text-text">Vector DB</p>
              <p className="text-[1.7vw] text-muted">FAISS for high-speed retrieval</p>
            </div>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.6vh]">
            <span className="w-[6vw] shrink-0 font-mono text-[2vw] font-extrabold text-primary">L3</span>
            <div>
              <p className="text-[2vw] font-semibold text-text">Rule Engine</p>
              <p className="text-[1.7vw] text-muted">Pure Python heuristics — no LLM black-boxes</p>
            </div>
          </div>
          <div className="flex items-center gap-[2vw] rounded-[0.8vw] border border-white/10 bg-white/[0.035] px-[2.2vw] py-[2.6vh]">
            <span className="w-[6vw] shrink-0 font-mono text-[2vw] font-extrabold text-accent">L4</span>
            <div>
              <p className="text-[2vw] font-semibold text-text">Validation</p>
              <p className="text-[1.7vw] text-muted">hashlib SHA-256 for byte-identical reproducibility</p>
            </div>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>07 / 10</span>
        </div>
      </div>
    </div>
  );
}
