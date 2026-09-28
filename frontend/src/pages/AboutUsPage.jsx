import React, { useState, useEffect, useRef } from 'react';
import {
  Compass,
  Award,
  ShieldCheck,
  Target,
  ArrowRight,
  ExternalLink,
  Layers,
  Database,
  FileText,
  AlertTriangle,
  BrainCircuit,
  Activity,
  CheckCircle2,
  ChevronRight,
  MapPin,
  Phone,
  Printer,
  Mail,
  Calendar,
  Eye,
  Building2,
  Check
} from 'lucide-react';

// Number counter animation component for key operational indicators
function AnimatedCounter({ end, duration = 1600, suffix = '', prefix = '' }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTimestamp = null;
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(easeProgress * end));
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        setCount(end);
      }
    };
    const animId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animId);
  }, [end, duration]);

  return (
    <span>
      {prefix}
      {count.toLocaleString()}
      {suffix}
    </span>
  );
}

// Gentle fade-up animation wrapper on scroll into viewport
function FadeInSection({ children, className = '' }) {
  const [isVisible, setVisible] = useState(false);
  const domRef = useRef();

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            if (domRef.current) observer.unobserve(domRef.current);
          }
        });
      },
      { threshold: 0.08 }
    );

    const currentRef = domRef.current;
    if (currentRef) observer.observe(currentRef);

    return () => {
      if (currentRef) observer.unobserve(currentRef);
    };
  }, []);

  return (
    <div
      ref={domRef}
      className={`transition-all duration-700 ease-out ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
      } ${className}`}
    >
      {children}
    </div>
  );
}

// Official Oil India Limited Logo Component
export function OilIndiaLogo({ size = 44, showText = true, textColor = 'text-[#17324D]' }) {
  return (
    <div className="flex items-center gap-3 select-none shrink-0" title="Oil India Limited (ऑयल इंडिया लिमिटेड)">
      <img
        src="/oil-india-logo.svg"
        alt="Oil India Limited"
        className="w-auto object-contain shrink-0"
        style={{ height: `${size}px` }}
      />

      {showText && (
        <div className="flex flex-col text-left leading-tight">
          <div className="flex items-baseline gap-1.5">
            <span className={`text-[15px] font-black tracking-tight uppercase ${textColor}`}>
              OIL INDIA LIMITED
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-[#D32F2F] uppercase font-mono tracking-wide">
              ऑयल इंडिया
            </span>
            <span className="text-[10px] text-[#64748B] font-medium hidden sm:inline">
              • Conquering Newer Horizons
            </span>
          </div>
        </div>
      )}
    </div>
  );
}


export default function AboutUsPage({ onNavigate }) {
  // Visual Flow: Operational Data Pipeline (Exploration to Intelligence)
  const intelligenceFlowSteps = [
    {
      step: '01',
      title: 'Exploration',
      subtitle: 'Field Geology & Seismic',
      desc: 'Subsurface seismic mapping, concession scouting, and exploratory well trajectory formulation.',
      icon: Compass,
      tag: 'Basin Scouting'
    },
    {
      step: '02',
      title: 'Drilling Data',
      subtitle: 'Real-Time Telemetry',
      desc: 'Sensor streams, MWD/LWD feeds, mud logs, and Daily Drilling Reports (DDR) captured at the rig site.',
      icon: Activity,
      tag: 'Sensor Telemetry'
    },
    {
      step: '03',
      title: 'Historical Knowledge',
      subtitle: 'WCR & Offset Memory',
      desc: 'Decades of verified Well Completion Reports (WCR) and 15,108 canonical master wells indexed dynamically.',
      icon: Database,
      tag: '15,108+ Master Wells'
    },
    {
      step: '04',
      title: 'Risk Intelligence',
      subtitle: 'Lookahead Hazard Models',
      desc: 'Machine learning lookahead models predicting mud losses, stuck pipe, kicks, and overpressure zones.',
      icon: AlertTriangle,
      tag: 'Calibrated Forecasting'
    },
    {
      step: '05',
      title: 'Engineer Decision Support',
      subtitle: 'Evidence-Based Action',
      desc: 'Human-in-the-loop engineering interface with 100% traceable citations empowering field superintendents.',
      icon: BrainCircuit,
      tag: 'Human In The Loop'
    }
  ];

  // NWIS Core Capabilities
  const capabilities = [
    {
      title: 'Nearby Well Intelligence',
      desc: 'High-speed spatial querying across public and dynamic wells, grouping offset wells by geodesic distance and basin proximity.',
      icon: Compass,
      tag: 'Spatial Lookahead'
    },
    {
      title: 'Offset Well Correlation',
      desc: 'Multivariate similarity matching on formation type, total depth, lithology classification, and drilling trajectory.',
      icon: Layers,
      tag: 'Stratigraphic Matching'
    },
    {
      title: 'Historical Event Analysis',
      desc: 'Deep indexing of past lost circulation, pipe sticking, overpressure, and torque anomalies with associated NPT hours.',
      icon: AlertTriangle,
      tag: 'NPT Reduction'
    },
    {
      title: 'Formation & Depth Correlation',
      desc: 'Stratigraphic lookahead window (±200m) to predict geological transitions before the bit penetrates vulnerable intervals.',
      icon: Database,
      tag: 'Pre-Spud Lookahead'
    },
    {
      title: 'WCR Extraction Pipeline',
      desc: 'Structured parsing, OCR extraction, and human-in-the-loop validation of legacy well completion reports and mud logs.',
      icon: FileText,
      tag: 'Automated Ingestion'
    },
    {
      title: 'Risk-Ahead Early Warning',
      desc: 'Calibrated early warning hazard forecasts for Mud Loss, Stuck Pipe, Kick, Overpressure, and Torque Spikes.',
      icon: Activity,
      tag: 'Hazard Prevention'
    },
    {
      title: 'Engineering Copilot RAG',
      desc: 'Semantic retrieval constrained strictly to verified institutional memory documents with traceable source citations.',
      icon: BrainCircuit,
      tag: 'Evidence Grounded'
    },
    {
      title: 'Live Telemetry & Diagnostics',
      desc: 'Real-time telemetry playback, observational sensor diagnostics, and alert acknowledgment workflows for operations.',
      icon: SparklesIcon,
      tag: 'Real-Time Awareness'
    }
  ];

  function SparklesIcon(props) {
    return <Activity {...props} />;
  }

  return (
    <div className="w-full min-h-screen bg-white text-[#17324D] font-sans pb-0 selection:bg-[#F58220] selection:text-white flex flex-col justify-between">
      {/* ============================================================== */}
      {/* MAIN CONTENT WRAPPER                                           */}
      {/* ============================================================== */}
      <div className="w-full space-y-12 sm:space-y-16">

        {/* ============================================================== */}
        {/* 1. HERO — OIL & GAS DRILLING FIELD AT SUNSET                   */}
        {/* ============================================================== */}
        <section className="relative w-full overflow-hidden bg-[#0A1626] min-h-[520px] sm:min-h-[580px] lg:min-h-[640px] flex items-center border-b border-[#D7E0E8]">
          {/* Background: Oil & Gas Drilling Field at Sunset */}
          <div
            className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat transition-transform duration-700 ease-out"
            style={{ backgroundImage: `url('/oilfield_hero.jpg')` }}
          />

          {/* Dark Cinematic Overlay Preserving Sunset & Ensuring Text Readability */}
          <div className="absolute inset-0 z-10 bg-gradient-to-t from-black/92 via-black/45 to-black/25" />

          {/* Hero Content */}
          <div className="relative z-20 max-w-[1440px] mx-auto px-5 sm:px-8 py-12 lg:py-16 w-full flex flex-col justify-between min-h-[520px] sm:min-h-[580px] lg:min-h-[640px]">
            {/* Top Row: MoPNG Government of India Official Logo & Corporate Trust Label */}
            <div className="flex flex-wrap items-center justify-between gap-4">
              {/* MoPNG Government of India Official Logo */}
              <a
                href="https://mopng.gov.in/en"
                target="_blank"
                rel="noopener noreferrer"
                title="Ministry of Petroleum and Natural Gas, Government of India (mopng.gov.in)"
                className="mopng-hero-logo inline-flex flex-col items-center bg-white px-3 py-1.5 sm:px-3.5 sm:py-2 rounded shadow-md border border-slate-200/90 transition-transform duration-300 hover:scale-[1.02] cursor-pointer group"
              >
                <img
                  src="/mopng-logo.png"
                  alt="Ministry of Petroleum and Natural Gas, Government of India"
                  className="w-[110px] sm:w-[135px] lg:w-[155px] h-auto object-contain"
                />
                <div className="text-[8.5px] sm:text-[9.5px] text-[#1E293B] font-semibold text-center leading-tight pt-1 border-t border-slate-200 mt-1 w-full font-sans">
                  Ministry of Petroleum and Natural Gas
                  <span className="block text-[8px] sm:text-[8.5px] text-[#64748B] font-normal">
                    Government of India
                  </span>
                </div>
              </a>

              {/* Small Unobtrusive Trust Label */}
              <div className="flex items-center gap-2 bg-black/60 border border-white/20 px-3 py-1.5 rounded text-xs font-mono font-medium tracking-wider text-slate-200 w-fit">
                <span className="w-2 h-2 rounded-full bg-[#D32F2F]" />
                <span>Oil India Limited</span>
                <span className="text-white/40">•</span>
                <span>India's National Exploration & Production Company</span>
              </div>
            </div>

            {/* Main Area: Text at Lower-Left */}
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-8 pt-8 sm:pt-12">
              {/* Lower-Left Text Container */}
              <div className="max-w-2xl lg:max-w-3xl space-y-3">
                <span className="text-xs sm:text-sm font-mono font-bold uppercase tracking-widest text-[#F58220] block drop-shadow-xs">
                  CONTINUOUS UPSTREAM HORIZONS
                </span>

                <h1 className="text-2xl sm:text-4xl lg:text-5xl font-black uppercase tracking-tight text-white leading-tight drop-shadow-md">
                  OIL INDIA LIMITED — ENERGY OPERATIONS ACROSS FRONTIER CONCESSIONS
                </h1>

                <p className="text-sm sm:text-base text-slate-200 font-normal leading-relaxed drop-shadow-sm max-w-2xl">
                  Safeguarding the nation’s energy security through sustained exploration, state-of-the-art drilling engineering, and environmental stewardship.
                </p>

                {/* Navigation Action Buttons */}
                <div className="pt-2 flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => onNavigate && onNavigate('map')}
                    className="px-5 py-2.5 rounded bg-[#0B5EA8] hover:bg-[#063B73] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-2 transition-colors cursor-pointer shadow-sm"
                  >
                    <Compass size={15} />
                    <span>Interactive Well Map</span>
                    <ArrowRight size={13} />
                  </button>

                  <button
                    onClick={() => {
                      const el = document.getElementById('about-oil-india');
                      if (el) el.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className="px-5 py-2.5 rounded bg-white/10 hover:bg-white/20 text-white font-bold text-xs uppercase tracking-wider border border-white/25 transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <span>About Oil India</span>
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </div>

            {/* Bottom Institutional Metric Strip */}
            <div className="mt-8 pt-5 border-t border-white/20 grid grid-cols-2 sm:grid-cols-4 gap-6 text-white">
              <div className="space-y-0.5">
                <div className="text-2xl sm:text-3xl font-black font-mono tracking-tight">
                  <AnimatedCounter end={15108} duration={1600} suffix="+" />
                </div>
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  Master Wells Cataloged
                </div>
              </div>

              <div className="space-y-0.5">
                <div className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-[#F58220]">
                  <AnimatedCounter end={65} duration={1400} suffix="+ Yrs" />
                </div>
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  Upstream Exploration
                </div>
              </div>

              <div className="space-y-0.5">
                <div className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-[#38BDF8]">
                  Maharatna
                </div>
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  Central Public Sector Enterprise
                </div>
              </div>

              <div className="space-y-0.5">
                <div className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-[#10B981]">
                  100%
                </div>
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  Traceable Evidence Grounding
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================== */}
        {/* 2. ABOUT OIL INDIA                                             */}
        {/* ============================================================== */}
        <FadeInSection>
          <section id="about-oil-india" className="max-w-[1440px] mx-auto px-5 sm:px-8">
            <div className="bg-white border border-[#D7E0E8] rounded-md p-6 sm:p-8 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-8">
              <div className="space-y-3 max-w-3xl">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#D32F2F]" />
                  <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider">
                    Corporate Overview
                  </span>
                </div>

                <h2 className="text-2xl sm:text-3xl font-black text-[#063B73] tracking-tight uppercase">
                  NATIONAL ENERGY HERITAGE & UPSTREAM EXCELLENCE
                </h2>

                <p className="text-xs sm:text-sm text-[#334155] leading-relaxed">
                  <strong>Oil India Limited (OIL)</strong> is a premier fully integrated National Oil Company under the administrative control of the Ministry of Petroleum and Natural Gas, Government of India. Awarded the prestigious <strong>Maharatna</strong> CPSE status, OIL is India’s second-largest national upstream hydrocarbon exploration and production enterprise.
                </p>

                <p className="text-xs sm:text-sm text-[#475569] leading-relaxed">
                  Tracing its operational roots to the historic commercial oil discovery in Digboi, Assam—the oldest operating oil well in Asia—OIL continues to expand its exploratory footprint across Upper Assam, Arunachal Pradesh, Rajasthan, Krishna-Godavari offshore, Mahanadi, and strategic overseas energy assets.
                </p>
              </div>

              {/* Official Oil India Identity Profile Card */}
              <div className="bg-[#F8FAFC] border border-[#D7E0E8] rounded-md p-5 flex flex-col justify-between space-y-3 shrink-0 lg:w-84">
                <OilIndiaLogo size={42} showText={true} textColor="text-[#063B73]" />
                <div className="text-[11px] text-[#64748B] space-y-1.5 border-t border-[#E2E8F0] pt-3">
                  <div className="flex justify-between">
                    <span>Enterprise Status:</span>
                    <span className="font-bold text-[#063B73]">Maharatna CPSE</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Administrative Ministry:</span>
                    <span className="font-semibold text-[#1E293B]">MoPNG, Govt. of India</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Operational Headquarters:</span>
                    <span className="font-medium text-[#1E293B]">Duliajan, Assam</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Registered Office:</span>
                    <span className="font-medium text-[#1E293B]">Noida, Uttar Pradesh</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Platform Application:</span>
                    <span className="font-bold text-[#0B5EA8]">NWIS Drilling Workstation</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 3. EXPLORATION / FIELD OPERATIONS & GEOLOGICAL R&D             */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8 space-y-5">
            <div className="border-b border-[#D7E0E8] pb-3 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
              <div>
                <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider block">
                  Upstream Value Chain
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
                  EXPLORATION & SUBSURFACE GEOSCIENCE
                </h2>
              </div>
              <span className="text-xs text-[#64748B] font-medium">
                Field Drilling Operations ● Geological Core Analysis
              </span>
            </div>

            {/* Clean Two-Column Corporate Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Column 1: Petroleum & Drilling Engineers */}
              <div className="bg-white border border-[#D7E0E8] rounded-md overflow-hidden shadow-xs flex flex-col justify-between group">
                <div className="relative aspect-[16/10] overflow-hidden bg-slate-900">
                  <img
                    src="/assets/about/drilling_engineers.jpg"
                    alt="Petroleum and Drilling Engineers at Work"
                    loading="lazy"
                    className="w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.02]"
                  />
                  <div className="absolute top-3 left-3 bg-black/75 border border-white/20 text-white text-[10px] font-mono font-bold px-2.5 py-1 rounded-sm">
                    UPSTREAM DRILLING OPERATIONS
                  </div>
                </div>

                <div className="p-6 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#D32F2F]" />
                    <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider">
                      Field Engineering
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-[#063B73]">
                    Exploration & Field Drilling Operations
                  </h3>
                  <p className="text-xs text-[#475569] leading-relaxed">
                    On-site drilling superintendents, mud engineers, and directional drillers execute complex frontier drilling campaigns. Rig floor telemetry oversight, drill-string dynamics, casing integrity, and real-time hydraulics management ensure safe, compliant penetration through hazardous subsurface intervals.
                  </p>
                </div>
              </div>

              {/* Column 2: Geological R&D */}
              <div className="bg-white border border-[#D7E0E8] rounded-md overflow-hidden shadow-xs flex flex-col justify-between group">
                <div className="relative aspect-[16/10] overflow-hidden bg-slate-900">
                  <img
                    src="/assets/about/geological_exploration.jpg"
                    alt="Geological R&D and Seismic Analysis"
                    loading="lazy"
                    className="w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.02]"
                  />
                  <div className="absolute top-3 left-3 bg-black/75 border border-white/20 text-white text-[10px] font-mono font-bold px-2.5 py-1 rounded-sm">
                    GEOSCIENCE RESEARCH & DEVELOPMENT
                  </div>
                </div>

                <div className="p-6 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#0B5EA8]" />
                    <span className="text-xs font-mono font-bold text-[#0B5EA8] uppercase tracking-wider">
                      Subsurface Geology
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-[#063B73]">
                    Geological R&D & Subsurface Exploration
                  </h3>
                  <p className="text-xs text-[#475569] leading-relaxed">
                    Advanced petroleum geology laboratories conducting multi-vintage 3D seismic volume analysis, rock core sample petrography, stratigraphic lookahead correlation, and pore pressure forecasting to delineate commercial reservoir pay zones prior to spudding.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 4. OPERATIONS — MIDSTREAM INFRASTRUCTURE & DIGITAL OILFIELD    */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8 space-y-5">
            <div className="border-b border-[#D7E0E8] pb-3 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
              <div>
                <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider block">
                  Production & Technology
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
                  OPERATIONS & DIGITAL INFRASTRUCTURE
                </h2>
              </div>
              <span className="text-xs text-[#64748B] font-medium">
                Surface Facilities ● Real-Time Cyber Operations
              </span>
            </div>

            {/* Equal-Sized Professional Corporate Cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Card 1: Midstream Infrastructure */}
              <div className="bg-white border border-[#D7E0E8] rounded-md overflow-hidden shadow-xs flex flex-col justify-between group">
                <div className="relative aspect-[16/10] overflow-hidden bg-slate-900">
                  <img
                    src="/assets/about/production_facility.jpg"
                    alt="Central Production Facility and Surface Infrastructure"
                    loading="lazy"
                    className="w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.02]"
                  />
                  <div className="absolute top-3 left-3 bg-black/75 border border-white/20 text-white text-[10px] font-mono font-bold px-2.5 py-1 rounded-sm">
                    SURFACE INFRASTRUCTURE & PIPELINES
                  </div>
                </div>

                <div className="p-6 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#D32F2F]" />
                    <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider">
                      Production Grid
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-[#063B73]">
                    Midstream Infrastructure & Surface Facilities
                  </h3>
                  <p className="text-xs text-[#475569] leading-relaxed">
                    Extensive crude oil stabilization units, natural gas processing facilities, separator banks, compressor manifolds, and cross-country pipeline networks delivering high-spec hydrocarbon streams from Northeast producing basins to national refining hubs.
                  </p>
                </div>
              </div>

              {/* Card 2: Digital Oilfield / Control Room */}
              <div className="bg-white border border-[#D7E0E8] rounded-md overflow-hidden shadow-xs flex flex-col justify-between group">
                <div className="relative aspect-[16/10] overflow-hidden bg-slate-900">
                  <img
                    src="/assets/about/control_room.jpg"
                    alt="Digital Drilling Real-Time Operations Control Room"
                    loading="lazy"
                    className="w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.02]"
                  />
                  <div className="absolute top-3 left-3 bg-black/75 border border-white/20 text-white text-[10px] font-mono font-bold px-2.5 py-1 rounded-sm">
                    REAL-TIME OPERATIONS CENTER (RTOC)
                  </div>
                </div>

                <div className="p-6 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#0B5EA8]" />
                    <span className="text-xs font-mono font-bold text-[#0B5EA8] uppercase tracking-wider">
                      Digital Operations
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-[#063B73]">
                    Digital Oilfield & Real-Time Cyber Operations
                  </h3>
                  <p className="text-xs text-[#475569] leading-relaxed">
                    Modern Real-Time Operations Centers (RTOC) featuring cyber-chair command stations, automated rate of penetration monitoring, continuous hookload and torque diagnostics, and high-frequency MWD/LWD streams to support operational decisions around the clock.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 5. INDUSTRIAL / ENGINEERING PHOTO STRIP (WIDE HORIZONTAL)      */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8">
            <div className="relative w-full h-64 sm:h-72 lg:h-80 rounded-md overflow-hidden border border-[#D7E0E8] shadow-xs group">
              <img
                src="/oilfield_hero.jpg"
                alt="Oil India Limited Onshore Energy Field Infrastructure"
                loading="lazy"
                className="w-full h-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.01]"
              />
              {/* Subtle Gradient Bottom Banner for Readability */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/35 to-transparent flex items-end p-6 sm:p-8">
                <div className="space-y-1 text-white">
                  <span className="text-[10px] sm:text-xs font-mono font-bold uppercase tracking-widest text-[#F58220] block">
                    CONTINUOUS UPSTREAM HORIZONS
                  </span>
                  <h3 className="text-lg sm:text-2xl font-black uppercase tracking-tight text-white">
                    Oil India Limited — Energy Operations across Frontier Concessions
                  </h3>
                  <p className="text-xs text-slate-300 max-w-2xl hidden sm:block">
                    Safeguarding the nation's energy security through sustained exploration, state-of-the-art drilling engineering, and environmental stewardship.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 6. VISION & MISSION (CLEAN CORPORATE CARDS)                    */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8 space-y-5">
            <div className="border-b border-[#D7E0E8] pb-3 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
              <div>
                <span className="text-xs font-mono font-bold text-[#D32F2F] uppercase tracking-wider block">
                  Corporate Governance
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
                  VISION & STRATEGIC MISSION
                </h2>
              </div>
              <span className="text-xs text-[#64748B] font-medium">
                Institutional Mandates & Operational Objectives
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-1">
              {/* Vision Card */}
              <div className="bg-white border border-[#D7E0E8] border-l-4 border-l-[#0B5EA8] rounded-md p-6 sm:p-8 shadow-xs flex flex-col justify-center space-y-3">
                <h3 className="text-xl sm:text-2xl font-black uppercase tracking-tight text-[#063B73]">
                  OUR VISION
                </h3>

                <blockquote className="text-sm sm:text-base font-semibold italic leading-relaxed text-[#1E293B]">
                  “Be a leading and future ready integrated energy company committed to sustainable energy security of India through performance excellence.”
                </blockquote>
              </div>

              {/* Mission Card */}
              <div className="bg-white border border-[#D7E0E8] border-l-4 border-l-[#D32F2F] rounded-md p-6 sm:p-8 shadow-xs flex flex-col justify-center space-y-3">
                <h3 className="text-xl sm:text-2xl font-black uppercase tracking-tight text-[#063B73]">
                  OUR MISSION
                </h3>

                <blockquote className="text-sm sm:text-base font-semibold italic leading-relaxed text-[#1E293B]">
                  “To explore, produce and transport crude oil and natural gas with superior quality standards, environmental stewardship, continuous technological innovation, and value creation for the nation.”
                </blockquote>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 7. NWIS — ENGINEERING INTELLIGENCE FOR DRILLING OPERATIONS      */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8 space-y-6">
            <div className="bg-white border border-[#D7E0E8] rounded-md p-6 sm:p-8 shadow-xs space-y-8">
              <div className="border-b border-[#E2E8F0] pb-4 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
                <div>
                  <span className="text-xs font-mono font-bold text-[#0B5EA8] uppercase tracking-wider block">
                    Integrated Engineering Technology
                  </span>
                  <h2 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
                    NWIS — ENGINEERING INTELLIGENCE FOR DRILLING OPERATIONS
                  </h2>
                </div>
                <span className="text-xs text-[#64748B] font-medium">
                  Cognitive Subsurface Lookahead & Risk Advisory
                </span>
              </div>

              <p className="text-xs sm:text-sm text-[#334155] leading-relaxed max-w-4xl">
                NWIS translates decades of historical well completion reports (WCR), daily drilling logs (DDR), lithological formations, and spatial offset data into predictive lookahead guidance for drilling engineers and superintendents.
              </p>

              {/* Visual Flow: From Exploration to Intelligence */}
              <div className="space-y-3">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#063B73]">
                  Operational Data Pipeline (Exploration → Decision Support)
                </span>

                <div className="grid grid-cols-1 md:grid-cols-5 gap-3.5 pt-1">
                  {intelligenceFlowSteps.map((step, idx) => {
                    const StepIcon = step.icon;
                    return (
                      <div
                        key={step.step}
                        className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-md p-4 flex flex-col justify-between space-y-3 hover:border-[#0B5EA8] transition-colors"
                      >
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-mono font-bold text-[#0B5EA8]">
                              STEP {step.step}
                            </span>
                            <div className="w-7 h-7 rounded bg-white border border-slate-200 text-[#063B73] flex items-center justify-center">
                              <StepIcon size={14} />
                            </div>
                          </div>

                          <div>
                            <h4 className="text-xs font-bold text-[#063B73]">
                              {step.title}
                            </h4>
                            <span className="text-[10px] font-semibold text-[#D32F2F]">
                              {step.subtitle}
                            </span>
                          </div>

                          <p className="text-[11px] text-[#64748B] leading-snug">
                            {step.desc}
                          </p>
                        </div>

                        <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
                          <span>{step.tag}</span>
                          {idx < intelligenceFlowSteps.length - 1 && (
                            <ArrowRight size={12} className="text-[#0B5EA8] hidden md:block" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* NWIS Capabilities Grid */}
              <div className="space-y-3 pt-2">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#063B73]">
                  Analytical Capabilities
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                  {capabilities.map((cap) => {
                    const Icon = cap.icon;
                    return (
                      <div
                        key={cap.title}
                        className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-md p-4 flex flex-col justify-between space-y-2 hover:border-[#0B5EA8] transition-colors"
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between">
                            <div className="w-8 h-8 rounded bg-white text-[#0B5EA8] flex items-center justify-center border border-slate-200">
                              <Icon size={16} />
                            </div>
                            <span className="text-[10px] font-mono font-bold text-[#0B5EA8] bg-white border border-slate-200 px-1.5 py-0.5 rounded">
                              {cap.tag}
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-[#063B73]">
                            {cap.title}
                          </h4>
                          <p className="text-[11px] text-[#64748B] leading-relaxed">
                            {cap.desc}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Non-Control Advisory Disclaimer Banner */}
              <div className="p-4 bg-[#EBF9F1] border-l-4 border-[#16834B] border-y border-r border-[#B7EBCA] rounded-r text-xs text-[#17324D] flex items-start gap-3">
                <ShieldCheck size={18} className="text-[#16834B] shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-[#16834B] uppercase tracking-wide text-[10px] block">
                    Engineering Decision Support Advisory
                  </span>
                  <span>
                    NWIS serves as a cognitive advisory workstation for drilling engineers and superintendents. It does not autonomously command rig machinery; operational drilling decisions remain under qualified engineering authority.
                  </span>
                </div>
              </div>
            </div>
          </section>
        </FadeInSection>

        {/* ============================================================== */}
        {/* 8. OFFICIAL OIL INDIA INSTITUTIONAL REFERENCES                 */}
        {/* ============================================================== */}
        <FadeInSection>
          <section className="max-w-[1440px] mx-auto px-5 sm:px-8">
            <div className="bg-white border border-[#D7E0E8] rounded-md p-5 sm:p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-0.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#063B73]">
                  Official Oil India Limited Institutional References
                </h3>
                <p className="text-xs text-[#64748B]">
                  Verified corporate information hosted on the official Oil India Limited institutional portal.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <a
                  href="https://www.oil-india.com/vision"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#F8FAFC] hover:bg-[#EAF5FB] text-[#063B73] hover:text-[#0B5EA8] border border-[#D7E0E8] text-xs font-bold px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors"
                >
                  <span>OIL Vision & Mission</span>
                  <ExternalLink size={12} />
                </a>

                <a
                  href="https://www.oil-india.com/who-we-are"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#F8FAFC] hover:bg-[#EAF5FB] text-[#063B73] hover:text-[#0B5EA8] border border-[#D7E0E8] text-xs font-bold px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors"
                >
                  <span>OIL Corporate Profile</span>
                  <ExternalLink size={12} />
                </a>

                <a
                  href="https://www.oil-india.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#F8FAFC] hover:bg-[#EAF5FB] text-[#063B73] hover:text-[#0B5EA8] border border-[#D7E0E8] text-xs font-bold px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors"
                >
                  <span>OIL Official Portal</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          </section>
        </FadeInSection>

      </div>

      {/* ============================================================== */}
      {/* 9. POLISHED CORPORATE FOOTER (5-COLUMN DARK STRUCTURE)         */}
      {/* ============================================================== */}
      <footer className="w-full bg-[#070D18] text-slate-300 pt-16 pb-12 mt-20 relative overflow-hidden border-t-2 border-transparent">
        {/* Glowing Gradient Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-[2.5px] bg-gradient-to-r from-[#0B5EA8] via-[#F58220] to-[#D32F2F] shadow-[0_0_15px_rgba(245,130,32,0.45)]" />

        {/* Ambient Top Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[250px] bg-[#0B5EA8]/10 blur-3xl rounded-full pointer-events-none" />

        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 relative z-10 space-y-12">
          {/* Main 5-Column Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 lg:gap-10">
            {/* COLUMN 1: CORPORATE OFFICE */}
            <div className="lg:col-span-4 space-y-5">
              <OilIndiaLogo size={42} showText={true} textColor="text-white" />

              <div className="space-y-1.5 pt-1">
                <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#F58220]">
                  Corporate Office
                </span>
                <h4 className="text-sm font-black uppercase text-white tracking-wide">
                  Oil India Limited
                </h4>
                <div className="text-xs text-slate-400 leading-relaxed flex items-start gap-2.5 pt-1">
                  <MapPin size={15} className="text-[#F58220] shrink-0 mt-0.5" />
                  <span>Plot No. 19, Near Film City, Sector 16A, Noida – 201301, India</span>
                </div>
              </div>

              <div className="space-y-2 pt-3 border-t border-slate-800/80 text-xs">
                <div className="flex items-center gap-2.5 text-slate-300">
                  <Phone size={13} className="text-[#38BDF8] shrink-0" />
                  <span className="text-slate-400">Phone:</span>
                  <a href="tel:01202419000" className="hover:text-white font-mono transition-colors">
                    0120 – 2419000
                  </a>
                </div>

                <div className="flex items-center gap-2.5 text-slate-300">
                  <Printer size={13} className="text-[#94A3B8] shrink-0" />
                  <span className="text-slate-400">Fax:</span>
                  <span className="font-mono text-slate-300">
                    0120 – 2488310
                  </span>
                </div>

                <div className="flex items-start gap-2.5 text-slate-300 pt-0.5">
                  <Mail size={13} className="text-[#F58220] shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <span className="text-slate-400 block text-[11px]">Email:</span>
                    <a
                      href="mailto:oilindia@oilindia.in"
                      className="hover:text-white font-mono text-[11px] block transition-colors text-slate-300"
                    >
                      oilindia[at]oilindia[dot]in
                    </a>
                    <a
                      href="mailto:webmaster@oilindia.in"
                      className="hover:text-white font-mono text-[11px] block transition-colors text-slate-300"
                    >
                      webmaster[at]oilindia[dot]in
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* COLUMN 2 */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white border-l-2 border-[#0B5EA8] pl-2.5">
                Governance & RTI
              </h4>
              <ul className="space-y-2.5 text-xs">
                <li>
                  <a
                    href="https://www.oil-india.com/rti"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>RTI</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/contact-us"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Contact Us</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>NorthEast Gas Subsidy</span>
                  </a>
                </li>
              </ul>
            </div>

            {/* COLUMN 3 */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white border-l-2 border-[#D32F2F] pl-2.5">
                Integrity & Ethics
              </h4>
              <ul className="space-y-2.5 text-xs">
                <li>
                  <a
                    href="https://www.oil-india.com/feedback"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Feedback</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/integrity-pact"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Integrity Pact</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Applicable Acts and Others</span>
                  </a>
                </li>
              </ul>
            </div>

            {/* COLUMN 4 */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white border-l-2 border-[#F58220] pl-2.5">
                Policies & Compliance
              </h4>
              <ul className="space-y-2.5 text-xs">
                <li>
                  <a
                    href="https://www.oil-india.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Complaint Handling System</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Preservation of Documents and Archival Policy</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Memorandum of Understanding</span>
                  </a>
                </li>
              </ul>
            </div>

            {/* COLUMN 5 */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white border-l-2 border-[#10B981] pl-2.5">
                Citizen's Charter
              </h4>
              <ul className="space-y-2.5 text-xs">
                <li>
                  <a
                    href="https://www.oil-india.com/citizens-charter"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Citizen's Charter</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://www.oil-india.com/website-policies"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-slate-400 hover:text-white hover:translate-x-1 transition-all duration-200 group"
                  >
                    <ChevronRight size={12} className="text-slate-600 group-hover:text-[#F58220] transition-colors" />
                    <span>Website Policies</span>
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* BOTTOM BAR */}
          <div className="border-t border-slate-800/80 pt-8 space-y-5 text-xs">
            {/* Policy Navigation Row */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-x-5 gap-y-2 text-[11px] font-medium text-slate-400">
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Terms & Conditions</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Privacy Policy</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Copyright Policy</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Hyperlinking Policy</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Disclaimer</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Accessibility Statement</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Help</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Sitemap</a>
              <span className="text-slate-700">•</span>
              <a href="https://www.oil-india.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Ownership Information</a>
            </div>

            {/* Copyright & Right-Side Stats Row */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800/50 text-[11px]">
              <div className="text-center sm:text-left space-y-0.5">
                <p className="text-slate-400">
                  Copyright © 2024 Oil India Limited. All Rights Reserved.
                </p>
                <p className="text-slate-500 text-[10px]">
                  Content owned & provided by Oil India Limited, India
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3.5 text-slate-400">
                <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded font-mono text-[10px]">
                  <Calendar size={12} className="text-[#38BDF8]" />
                  <span>Last Updated: <span className="text-white font-semibold">28-Sep-2026</span></span>
                </div>

                <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded font-mono text-[10px]">
                  <Eye size={12} className="text-[#10B981]" />
                  <span>Visitors Counter: <span className="text-[#10B981] font-bold">1,842,910</span></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
