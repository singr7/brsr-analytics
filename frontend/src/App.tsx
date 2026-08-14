import { DemoChart } from './components/DemoChart'
import { HealthFooter } from './components/HealthFooter'

export default function App() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_#dceee3,_transparent_42%)]">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-7">
        <div className="text-xl font-semibold tracking-tight">BRSR Lens</div>
        <span className="rounded-full border border-emerald-900/20 px-3 py-1 text-xs uppercase tracking-widest">Foundation</span>
      </header>
      <main className="mx-auto grid max-w-6xl gap-8 px-6 pb-16 pt-14 lg:grid-cols-[1fr_1.15fr]">
        <section className="self-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.24em] text-emerald-700">Disclosure intelligence</p>
          <h1 className="m-0 text-5xl font-semibold leading-tight tracking-tight">See the substance behind sustainability reporting.</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-emerald-950/70">Traceable BRSR analytics, filing preparation, and assurance readiness in one disciplined platform.</p>
        </section>
        <section className="rounded-3xl border border-white/70 bg-white/80 p-6 shadow-xl shadow-emerald-950/10 backdrop-blur">
          <div className="mb-5 flex items-baseline justify-between">
            <div>
              <p className="m-0 text-sm text-emerald-950/60">Illustrative portfolio</p>
              <h2 className="m-0 mt-1 text-2xl">BRSR readiness</h2>
            </div>
            <span className="text-sm text-emerald-700">FY 2025–26</span>
          </div>
          <DemoChart />
        </section>
      </main>
      <HealthFooter />
    </div>
  )
}

