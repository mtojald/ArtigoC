
import time
import sys
import os
import platform
import random
import argparse
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# ── Importações condicionais ──────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[AVISO] psutil não instalado. Execute: pip install psutil")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.progress import BarColumn, Progress, TextColumn
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("[AVISO] rich não instalado. Execute: pip install rich")

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_COUNT = pynvml.nvmlDeviceGetCount()
    HAS_NVML = True
except Exception:
    HAS_NVML = False
    GPU_COUNT = 0

# ── Constantes de escalonamento térmico ─────────────────────────
TEMP_NORMAL   = 40.0   # °C — zona segura
TEMP_ATENCAO  = 60.0   # °C — reduzir carga
TEMP_CRITICO  = 75.0   # °C — migrar tarefas
TEMP_HOTSPOT  = 85.0   # °C — shutdown preventivo
HISTORY_SIZE  = 60     # amostras para histórico (60 s)


# ══════════════════════════════════════════════════════════════════
# Coleta de temperatura
# ══════════════════════════════════════════════════════════════════

@dataclass
class CpuSensor:
    label: str
    temp:  float
    high:  Optional[float] = None
    crit:  Optional[float] = None


def get_cpu_temps() -> list[CpuSensor]:
    """Lê temperaturas reais da CPU via psutil (Linux/macOS/Windows)."""
    sensors: list[CpuSensor] = []

    if not HAS_PSUTIL:
        return _simulate_sensors()

    # psutil.sensors_temperatures() só existe em Linux e macOS
    if not hasattr(psutil, "sensors_temperatures"):
        return _simulate_sensors("psutil sem suporte a sensores neste SO")

    raw = psutil.sensors_temperatures()
    if not raw:
        return _simulate_sensors("nenhum sensor detectado")


    priority = ["coretemp", "k10temp", "acpitz", "cpu_thermal"]
    chosen_key = None
    for key in priority:
        if key in raw:
            chosen_key = key
            break
    if chosen_key is None:
        chosen_key = list(raw.keys())[0]

    for entry in raw[chosen_key]:
        sensors.append(CpuSensor(
            label=entry.label or chosen_key,
            temp=entry.current,
            high=entry.high,
            crit=entry.critical,
        ))

    return sensors if sensors else _simulate_sensors("sem leituras válidas")


def _simulate_sensors(reason: str = "") -> list[CpuSensor]:
    """Gera temperaturas simuladas quando hardware não está disponível."""
    base = random.uniform(38, 62)
    label = f"[SIM{(' – ' + reason) if reason else ''}]"
    return [
        CpuSensor(f"Core 0 {label}", base + random.uniform(-4, 4), 80, 100),
        CpuSensor(f"Core 1 {label}", base + random.uniform(-4, 8), 80, 100),
        CpuSensor(f"Core 2 {label}", base + random.uniform(-2, 6), 80, 100),
        CpuSensor(f"Core 3 {label}", base + random.uniform(-3, 12), 80, 100),
    ]


def get_gpu_temps() -> list[tuple[str, float]]:
    """Lê temperaturas de GPUs NVIDIA via pynvml."""
    if not HAS_NVML:
        return []
    gpus = []
    for i in range(GPU_COUNT):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        name   = pynvml.nvmlDeviceGetName(handle)
        temp   = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        gpus.append((f"GPU {i} – {name}", float(temp)))
    return gpus


def get_cpu_usage() -> list[float]:
    """Retorna uso por núcleo (%)."""
    if not HAS_PSUTIL:
        return [random.uniform(10, 95) for _ in range(4)]
    return psutil.cpu_percent(percpu=True)


def get_memory_usage() -> tuple[float, float, float]:
    """Retorna (total GB, usado GB, %)."""
    if not HAS_PSUTIL:
        return (16.0, random.uniform(4, 12), random.uniform(25, 75))
    m = psutil.virtual_memory()
    return (m.total / 1e9, m.used / 1e9, m.percent)



@dataclass
class SchedulingDecision:
    action:      str    
    reason:      str
    max_temp:    float
    pue_est:     float  
    color:       str   


def thermal_scheduling_decision(sensors: list[CpuSensor],
                                 history: deque) -> SchedulingDecision:
    """
    Implementa a lógica de decisão de escalonamento térmico descrita
    no artigo, baseada nos limiares de Nguyen et al. (2024).

    O PUE é estimado linearmente entre 1.26 (temp normal) e 1.80
    (hotspot), refletindo o impacto do esforço de refrigeração.
    """
    if not sensors:
        return SchedulingDecision("NORMAL", "sem sensores", 0, 1.26, "green")

    max_temp = max(s.temp for s in sensors)
    avg_temp = sum(s.temp for s in sensors) / len(sensors)


    trend = ""
    if len(history) >= 2:
        recent = list(history)[-10:]
        delta = recent[-1] - recent[0]
        trend = f" (↑ {delta:+.1f}°C/10 s)" if delta > 1 else \
                f" (↓ {delta:+.1f}°C/10 s)" if delta < -1 else " (estável)"


    if max_temp <= TEMP_NORMAL:
        pue = 1.26
        action, color = "NORMAL", "green"
        reason = f"Temperatura normal ({max_temp:.1f}°C ≤ {TEMP_NORMAL}°C){trend}"
    elif max_temp <= TEMP_ATENCAO:
        t = (max_temp - TEMP_NORMAL) / (TEMP_ATENCAO - TEMP_NORMAL)
        pue = 1.26 + t * (1.45 - 1.26)
        action, color = "MONITORAR", "yellow"
        reason = f"Temperatura em atenção ({max_temp:.1f}°C){trend}"
    elif max_temp <= TEMP_CRITICO:
        t = (max_temp - TEMP_ATENCAO) / (TEMP_CRITICO - TEMP_ATENCAO)
        pue = 1.45 + t * (1.65 - 1.45)
        action, color = "REDUZIR CARGA", "orange3"
        reason = f"Escalonar delay-tolerant workloads ({max_temp:.1f}°C){trend}"
    elif max_temp <= TEMP_HOTSPOT:
        t = (max_temp - TEMP_CRITICO) / (TEMP_HOTSPOT - TEMP_CRITICO)
        pue = 1.65 + t * (1.80 - 1.65)
        action, color = "MIGRAR TAREFAS", "red"
        reason = f"HOTSPOT detectado — migração imediata ({max_temp:.1f}°C){trend}"
    else:
        pue = 1.80
        action, color = "⚠ SHUTDOWN PREVENTIVO", "red"
        reason = f"TEMPERATURA CRÍTICA ({max_temp:.1f}°C > {TEMP_HOTSPOT}°C){trend}"

    return SchedulingDecision(action, reason, max_temp, pue, color)



@dataclass
class ClusterNode:
    name:  str
    temps: list[float] = field(default_factory=list)
    load:  float = 0.0

    @property
    def max_temp(self) -> float:
        return max(self.temps) if self.temps else 0.0


def simulate_cluster(n_nodes: int = 6) -> list[ClusterNode]:
    """Simula um cluster HPC com n_nodes nós, replicando o mapa térmico do artigo."""

    profiles = [
        ("Nó-A", 32, 4),
        ("Nó-B", 51, 5),
        ("Nó-C", 67, 6),   
        ("Nó-D", 74, 4),   
        ("Nó-E", 47, 5),
        ("Nó-F", 31, 3),
    ]
    nodes = []
    for name, base, ncores in profiles[:n_nodes]:
        cores = [base + random.gauss(0, 2) for _ in range(ncores)]
        load  = min(100, max(0, (base - 30) * 1.5 + random.gauss(0, 5)))
        nodes.append(ClusterNode(name=name, temps=cores, load=load))
    return nodes



def temp_bar(temp: float, width: int = 20) -> Text:
    """Barra de temperatura colorida."""
    filled = int(min(temp / 100.0, 1.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    if   temp < TEMP_NORMAL:  color = "green"
    elif temp < TEMP_ATENCAO: color = "yellow"
    elif temp < TEMP_CRITICO: color = "orange3"
    else:                     color = "red"
    return Text(f"{bar} {temp:5.1f}°C", style=color)


def render_once(console: Console):
    """Renderiza uma leitura única e sai."""
    sensors  = get_cpu_temps()
    gpus     = get_gpu_temps()
    decision = thermal_scheduling_decision(sensors, deque())
    cpu_pct  = get_cpu_usage()
    mem_tot, mem_used, mem_pct = get_memory_usage()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    tbl = Table(title="Sensores de Temperatura", box=box.ROUNDED,
                border_style="bright_blue", show_lines=True)
    tbl.add_column("Sensor",      style="cyan", min_width=30)
    tbl.add_column("Temperatura", min_width=32)
    tbl.add_column("High",        justify="right", style="yellow")
    tbl.add_column("Crítico",     justify="right", style="red")
    tbl.add_column("Zona",        justify="center")

    for s in sensors:
        zone = ("🟢 NORMAL"   if s.temp < TEMP_NORMAL  else
                "🟡 ATENÇÃO"  if s.temp < TEMP_ATENCAO else
                "🟠 CRÍTICO"  if s.temp < TEMP_CRITICO else
                "🔴 HOTSPOT")
        tbl.add_row(
            s.label,
            temp_bar(s.temp),
            f"{s.high:.0f}°C"  if s.high else "—",
            f"{s.crit:.0f}°C"  if s.crit else "—",
            zone,
        )

    for name, temp in gpus:
        zone = ("🟢 NORMAL"   if temp < TEMP_NORMAL  else
                "🟡 ATENÇÃO"  if temp < TEMP_ATENCAO else
                "🟠 CRÍTICO"  if temp < TEMP_CRITICO else
                "🔴 HOTSPOT")
        tbl.add_row(name, temp_bar(temp), "—", "—", zone)

    dec_text = (
        f"  Ação:    [{decision.color}]{decision.action}[/]\n"
        f"  Motivo:  {decision.reason}\n"
        f"  Temp max: {decision.max_temp:.1f}°C\n"
        f"  PUE est.: [bold]{decision.pue_est:.4f}[/]"
        f"  ({'↑ ineficiente' if decision.pue_est > 1.5 else '✓ eficiente'})"
    )

    cpu_rows = []
    for i, pct in enumerate(cpu_pct):
        bar_w = int(pct / 5)
        bar = "▮" * bar_w + "▯" * (20 - bar_w)
        color = "red" if pct > 90 else "yellow" if pct > 70 else "green"
        cpu_rows.append(f"  Core {i:02d}: [{color}]{bar}[/] {pct:5.1f}%")

    cpu_text = "\n".join(cpu_rows)

    console.print()
    console.print(Panel(
        f"[bold bright_white]HPC Thermal Monitor[/]  ·  {ts}\n"
        f"[dim]Baseado em: Nguyen et al. (2024) · Carrasco-Codina et al. (2026)[/]",
        border_style="bright_blue", expand=False
    ))
    console.print(tbl)
    console.print(Panel(dec_text, title="[bold]Decisão de Escalonamento Térmico[/]",
                        border_style=decision.color, expand=False))
    console.print(Panel(
        cpu_text +
        f"\n\n  Memória: {mem_used:.1f} GB / {mem_tot:.1f} GB  ({mem_pct:.1f}%)",
        title="[bold]Uso de Recursos[/]", border_style="bright_blue", expand=False
    ))




def render_cluster(console: Console):
    """Simula e exibe o mapa térmico de um cluster multi-nó."""
    console.print(Panel(
        "[bold]Simulação de Cluster HPC — Mapa Térmico[/]\n"
        "[dim]Baseado na Figura 2 do artigo (Nguyen et al., 2024)[/]",
        border_style="bright_blue"
    ))

    for _ in range(10): 
        nodes = simulate_cluster()

        tbl = Table(box=box.ROUNDED, border_style="bright_blue",
                    title=f"[dim]{datetime.now().strftime('%H:%M:%S')}[/]  Cluster Térmico")
        tbl.add_column("Nó",       style="cyan")
        tbl.add_column("Temp Máx", min_width=28)
        tbl.add_column("Carga %",  justify="right")
        tbl.add_column("Ação",     justify="center")

        for node in nodes:
            decision = thermal_scheduling_decision(
                [CpuSensor(f"c{i}", t) for i, t in enumerate(node.temps)],
                deque()
            )
            load_bar = "▮" * int(node.load / 5) + "▯" * (20 - int(node.load / 5))
            lc = "red" if node.load > 90 else "yellow" if node.load > 70 else "green"
            tbl.add_row(
                node.name,
                temp_bar(node.max_temp),
                f"[{lc}]{load_bar}[/] {node.load:.0f}%",
                f"[{decision.color}]{decision.action}[/]",
            )

        console.clear()
        console.print(Panel(
            "[bold]Simulação de Cluster HPC — Mapa Térmico[/]\n"
            "[dim]Reproduz a Figura 2 do artigo. Pressione Ctrl+C para sair.[/]",
            border_style="bright_blue"
        ))
        console.print(tbl)
        console.print()
        time.sleep(2)




def run_continuous(console: Console, interval: float = 2.0):
    """Atualiza o dashboard a cada `interval` segundos."""
    history: deque[float] = deque(maxlen=HISTORY_SIZE)

    console.print("[dim]Monitoramento contínuo iniciado. Pressione Ctrl+C para sair.[/]\n")

    try:
        while True:
            sensors  = get_cpu_temps()
            gpus     = get_gpu_temps()
            if sensors:
                history.append(max(s.temp for s in sensors))
            decision = thermal_scheduling_decision(sensors, history)
            cpu_pct  = get_cpu_usage()
            mem_tot, mem_used, mem_pct = get_memory_usage()
            ts = datetime.now().strftime("%H:%M:%S")


            spark = ""
            if history:
                mn, mx = min(history), max(history)
                chars = " ▁▂▃▄▅▆▇█"
                for v in list(history)[-40:]:
                    idx = int((v - mn) / max(mx - mn, 1) * 8)
                    spark += chars[idx]

            tbl = Table(box=box.SIMPLE_HEAVY, border_style="bright_blue",
                        expand=True, show_header=True)
            tbl.add_column("Sensor",      style="cyan", ratio=3)
            tbl.add_column("Temperatura", ratio=3)
            tbl.add_column("Zona",        justify="center", ratio=2)

            for s in sensors:
                zone = ("🟢 NORMAL"   if s.temp < TEMP_NORMAL  else
                        "🟡 ATENÇÃO"  if s.temp < TEMP_ATENCAO else
                        "🟠 CRÍTICO"  if s.temp < TEMP_CRITICO else
                        "🔴 HOTSPOT")
                tbl.add_row(s.label, temp_bar(s.temp), zone)
            for name, temp in gpus:
                zone = ("🟢 NORMAL" if temp < TEMP_NORMAL else
                        "🟡 ATENÇÃO" if temp < TEMP_ATENCAO else
                        "🟠 CRÍTICO" if temp < TEMP_CRITICO else
                        "🔴 HOTSPOT")
                tbl.add_row(name, temp_bar(temp), zone)

            content = (
                f"{tbl}\n"
                f"  [bold]Ação:[/] [{decision.color}]{decision.action}[/]  "
                f"[dim]PUE est.: {decision.pue_est:.4f}[/]\n"
                f"  [dim]{decision.reason}[/]\n"
                f"  [dim]Histórico (60 s): {spark}[/]\n"
                f"  Memória: {mem_used:.1f}/{mem_tot:.1f} GB ({mem_pct:.1f}%)  "
                f"  [dim]{ts}[/]"
            )

            console.clear()
            console.print(Panel(content,
                title="[bold bright_white]⚡ HPC Thermal Monitor[/]",
                border_style=decision.color, expand=True))
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Monitor encerrado.[/]")



def run_plain():
    """Saída simples para terminais sem rich."""
    sensors = get_cpu_temps()
    print(f"\n{'='*60}")
    print("  HPC Thermal Monitor  —  Leitura de Temperatura da CPU")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    for s in sensors:
        zone = ("NORMAL"   if s.temp < TEMP_NORMAL  else
                "ATENÇÃO"  if s.temp < TEMP_ATENCAO else
                "CRÍTICO"  if s.temp < TEMP_CRITICO else
                "HOTSPOT")
        bar = "█" * int(s.temp / 5) + "░" * (20 - int(s.temp / 5))
        print(f"  {s.label:<35} {bar} {s.temp:5.1f}°C  [{zone}]")

    d = thermal_scheduling_decision(sensors, deque())
    print(f"\n  Decisão: {d.action}")
    print(f"  Motivo : {d.reason}")
    print(f"  PUE est: {d.pue_est:.4f}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="HPC Thermal Monitor — Thermal-Aware Scheduling Demo"
    )
    parser.add_argument("--once",     action="store_true",
                        help="Faz uma leitura única e encerra")
    parser.add_argument("--simulate", action="store_true",
                        help="Simula cluster multi-nó (mapa térmico do artigo)")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Intervalo entre leituras em segundos (padrão: 2)")
    args = parser.parse_args()

    if not HAS_RICH:
        run_plain()
        return

    console = Console()

    if args.simulate:
        render_cluster(console)
    elif args.once:
        render_once(console)
    else:
        run_continuous(console, interval=args.interval)


if __name__ == "__main__":
    main()