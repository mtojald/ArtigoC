# HPC Thermal Monitor

Monitor térmico para ambientes de **High Performance Computing (HPC)** com suporte a monitoramento de CPU/GPU, análise térmica, estimativa de eficiência energética (PUE) e simulação de escalonamento térmico baseada em temperatura.

O projeto implementa um modelo de tomada de decisão para gerenciamento de carga computacional, permitindo identificar condições de operação normais, estados de atenção, situações críticas e hotspots térmicos.

---

## Funcionalidades

- Monitoramento de temperatura da CPU em tempo real.
- Monitoramento de GPUs NVIDIA via NVML.
- Coleta de uso de CPU por núcleo.
- Coleta de utilização de memória RAM.
- Estimativa de PUE (Power Usage Effectiveness).
- Classificação térmica em zonas:
  - 🟢 Normal
  - 🟡 Atenção
  - 🟠 Crítico
  - 🔴 Hotspot
- Decisão automática de escalonamento térmico.
- Dashboard interativo utilizando Rich.
- Simulação de cluster HPC multi-nó.
- Fallback para execução em terminais sem Rich.
- Simulação automática de sensores quando não há acesso ao hardware.

---

## Tecnologias Utilizadas

- Python 3.10+
- psutil
- rich
- pynvml (opcional)

---

## Instalação

Clone o repositório:

```bash
git clone https://github.com/mtojald/ArtigoC.git
cd hpc-thermal-monitor
```

Instale as dependências:

```bash
pip install rich psutil pynvml
```

Ou utilizando:

```bash
pip install -r requirements.txt
```

---

## Dependências

### psutil

Responsável por:

- Temperatura da CPU
- Uso de CPU
- Uso de memória

Instalação:

```bash
pip install psutil
```

### rich

Responsável pela interface visual no terminal.

Instalação:

```bash
pip install rich
```

### pynvml

Responsável pela leitura de temperatura de GPUs NVIDIA.

Instalação:

```bash
pip install pynvml
```

---

## Modos de Execução

### 1. Leitura Única

Realiza uma única coleta de dados e encerra o programa.

```bash
python monitor.py --once
```

Exibe:

- Temperaturas
- Estado térmico
- Uso de CPU
- Uso de memória
- Decisão de escalonamento

---

### 2. Monitoramento Contínuo

Executa um dashboard em tempo real.

```bash
python monitor.py
```

ou

```bash
python monitor.py --interval 5
```

onde:

- `--interval` define o intervalo entre atualizações em segundos.

---

### 3. Simulação de Cluster HPC

Executa uma simulação de múltiplos nós computacionais.

```bash
python monitor.py --simulate
```

A simulação gera:

- Temperaturas por nó
- Carga computacional
- Identificação de hotspots
- Recomendações de escalonamento

---

## Modelo de Escalonamento Térmico

O sistema utiliza quatro faixas térmicas:

| Faixa | Temperatura | Ação |
|---------|---------|---------|
| Normal | ≤ 40°C | Operação normal |
| Atenção | 40°C – 60°C | Monitoramento |
| Crítico | 60°C – 75°C | Redução de carga |
| Hotspot | 75°C – 85°C | Migração de tarefas |
| Emergência | > 85°C | Shutdown preventivo |

---

## Estimativa de PUE

O sistema estima o Power Usage Effectiveness (PUE) de acordo com a temperatura máxima observada.

Valores aproximados:

| Estado | PUE |
|----------|----------|
| Normal | 1.26 |
| Atenção | 1.26 – 1.45 |
| Crítico | 1.45 – 1.65 |
| Hotspot | 1.65 – 1.80 |

Quanto menor o PUE, maior a eficiência energética do ambiente.

---

## Estrutura do Projeto

```text
.
├── monitor.py
├── README.md
├── requirements.txt
```

Principais componentes:

| Componente | Função |
|------------|---------|
| CpuSensor | Armazena dados de sensores |
| SchedulingDecision | Armazena decisões térmicas |
| ClusterNode | Representa um nó do cluster |
| get_cpu_temps() | Coleta temperaturas da CPU |
| get_gpu_temps() | Coleta temperaturas da GPU |
| thermal_scheduling_decision() | Gera decisão de escalonamento |
| render_once() | Exibe leitura única |
| render_cluster() | Executa simulação |
| run_continuous() | Dashboard contínuo |

---

## Exemplo de Saída

```text
Ação: REDUZIR CARGA

Motivo:
Escalonar delay-tolerant workloads (68.3°C)

Temperatura máxima:
68.3°C

PUE estimado:
1.57
```

---

## Referências

O modelo implementado foi inspirado em estudos sobre gerenciamento térmico e eficiência energética em ambientes HPC:

- Nguyen et al. (2024)
- Carrasco-Codina et al. (2026)

---

## Licença

Este projeto é disponibilizado para fins acadêmicos e educacionais.


## Relatório + Artigo
[Relatório Individual Artigo.pdf](https://github.com/user-attachments/files/28918618/Relatorio.Individual.Artigo.pdf)  
[Artigo-MiguelTojal.docx.pdf](https://github.com/user-attachments/files/28918619/Artigo-MiguelTojal.docx.pdf)  

