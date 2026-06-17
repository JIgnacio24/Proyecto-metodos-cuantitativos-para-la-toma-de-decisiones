import { Component, signal, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Chart, ChartConfiguration, registerables } from 'chart.js';
import { DssService } from '../../services/dss.service';
import { ParametrosAnalisis, ResultadoCompleto, HistogramaData, CDFData, PronosticoResult } from '../../models/dss.models';

// Registrar todos los módulos de Chart.js (escalas, elementos, plugins)
Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  imports: [FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnDestroy {
  private readonly dss = inject(DssService);

  // ── Estado reactivo de la UI ────────────────────────────────────────────────
  cargando = signal(false);
  error    = signal<string | null>(null);
  resultado = signal<ResultadoCompleto | null>(null);
  tabActiva = signal<'pronostico' | 'inventario' | 'simulacion' | 'comparacion'>('pronostico');

  // ── Valores del formulario ──────────────────────────────────────────────────
  numeroPeriodos = 12;
  demandasPorPeriodo: number[] = [420, 445, 410, 460, 480, 435, 500, 470, 515, 490, 530, 505];
  costoUnitario        = 15000;
  precioVenta          = 28000;
  costoPorPedido       = 85000;
  costoMantener        = 2500;
  costoRuptura         = 12000;
  leadTime             = 2;
  nivelServicio        = 0.95;
  nIteraciones         = 10000;
  factorIncertidumbre  = 1.0;

  // Errores de validación por campo (clave = nombre del campo)
  errores: Record<string, string> = {};

  // Instancias activas de Chart.js, agrupadas por id de canvas
  private readonly graficos = new Map<string, Chart>();

  // ── Acciones del usuario ────────────────────────────────────────────────────

  /**
   * Ajusta el array de demandas al nuevo número de períodos.
   * Conserva los valores ya ingresados y rellena con 0 los períodos nuevos.
   */
  ajustarPeriodos(): void {
    this.numeroPeriodos = Math.max(3, Math.min(60, this.numeroPeriodos));
    const prev = this.demandasPorPeriodo;
    this.demandasPorPeriodo = Array.from({ length: this.numeroPeriodos }, (_, i) => prev[i] ?? 0);
  }

  /** Actualiza el valor de un período individual (binding seguro con @for + $index). */
  actualizarDemanda(i: number, valor: string): void {
    this.demandasPorPeriodo[i] = Math.max(0, parseFloat(valor) || 0);
  }

  /** Carga los parámetros de ejemplo desde el backend y los pone en el formulario. */
  cargarEjemplo(): void {
    this.dss.obtenerDatosEjemplo().subscribe({
      next: (datos: any) => {
        const historica = datos.demanda_historica as number[];
        this.numeroPeriodos = historica.length;
        this.demandasPorPeriodo = [...historica];
        this.costoUnitario       = datos.costo_unitario;
        this.precioVenta         = datos.precio_venta;
        this.costoPorPedido      = datos.costo_por_pedido;
        this.costoMantener       = datos.costo_mantener;
        this.costoRuptura        = datos.costo_ruptura;
        this.leadTime            = datos.lead_time;
        this.nivelServicio       = datos.nivel_servicio;
        this.nIteraciones        = datos.n_iteraciones;
        this.factorIncertidumbre = datos.factor_incertidumbre;
      },
      error: () => this.error.set('No se pudo conectar con el backend. Verificá que esté corriendo en localhost:8000'),
    });
  }

  /** Ejecuta el análisis completo llamando al endpoint /api/analizar. */
  analizar(): void {
    if (!this.validarFormulario()) return;
    const demandas = this.parsearDemandas();

    const params: ParametrosAnalisis = {
      demanda_historica:    demandas,
      costo_unitario:       this.costoUnitario,
      precio_venta:         this.precioVenta,
      costo_por_pedido:     this.costoPorPedido,
      costo_mantener:       this.costoMantener,
      costo_ruptura:        this.costoRuptura,
      lead_time:            this.leadTime,
      nivel_servicio:       this.nivelServicio,
      n_iteraciones:        this.nIteraciones,
      factor_incertidumbre: this.factorIncertidumbre,
    };

    this.cargando.set(true);
    this.error.set(null);

    this.dss.analizar(params).subscribe({
      next: (res) => {
        this.resultado.set(res);
        this.cargando.set(false);
        // Dar tiempo a Angular para actualizar el DOM antes de dibujar los charts
        setTimeout(() => this.renderizarGraficosTab(this.tabActiva()), 150);
      },
      error: (err) => {
        const detalle = err.error?.detail ?? 'Error al conectar con el servidor.';
        this.error.set(typeof detalle === 'string' ? detalle : JSON.stringify(detalle));
        this.cargando.set(false);
      },
    });
  }

  /** Cambia la pestaña activa y renderiza sus gráficos si hay resultados. */
  cambiarTab(tab: string): void {
    this.tabActiva.set(tab as 'pronostico' | 'inventario' | 'simulacion' | 'comparacion');
    if (this.resultado()) {
      setTimeout(() => this.renderizarGraficosTab(tab), 100);
    }
  }

  /** Re-ejecuta el análisis al cambiar un slider (para sensibilidad en vivo). */
  reanalizarSiHayResultados(): void {
    if (this.resultado()) this.analizar();
  }

  // ── Utilidades de formato ───────────────────────────────────────────────────

  /** Formatea un número como moneda en CRC con separador de miles. */
  crc(valor: number): string {
    return new Intl.NumberFormat('es-CR', {
      style: 'currency',
      currency: 'CRC',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(valor);
  }

  /** Formatea un número como porcentaje con un decimal. */
  pct(valor: number): string {
    return `${valor.toFixed(1)}%`;
  }

  /** Formatea un número con separador de miles y sin decimales. */
  num(valor: number): string {
    return new Intl.NumberFormat('es-CR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(valor);
  }

  // ── Lógica interna ──────────────────────────────────────────────────────────

  private validarFormulario(): boolean {
    const e: Record<string, string> = {};

    if (this.demandasPorPeriodo.length < 3)
      e['demanda'] = 'Se necesitan al menos 3 períodos de demanda histórica.';

    if (!this.costoUnitario || this.costoUnitario <= 0)
      e['costoUnitario'] = 'Campo obligatorio, debe ser mayor a 0.';

    if (!this.precioVenta || this.precioVenta <= 0)
      e['precioVenta'] = 'Campo obligatorio, debe ser mayor a 0.';
    else if (this.costoUnitario > 0 && this.precioVenta <= this.costoUnitario)
      e['precioVenta'] = 'Debe ser mayor al costo unitario.';

    if (!this.costoPorPedido || this.costoPorPedido <= 0)
      e['costoPorPedido'] = 'Campo obligatorio, debe ser mayor a 0.';

    if (!this.costoMantener || this.costoMantener <= 0)
      e['costoMantener'] = 'Campo obligatorio, debe ser mayor a 0.';

    if (!this.costoRuptura || this.costoRuptura <= 0)
      e['costoRuptura'] = 'Campo obligatorio, debe ser mayor a 0.';

    if (!this.leadTime || this.leadTime < 1)
      e['leadTime'] = 'Mínimo 1 período de reposición.';

    this.errores = e;
    return Object.keys(e).length === 0;
  }

  private parsearDemandas(): number[] {
    return this.demandasPorPeriodo.map(d => Math.max(0, Number(d) || 0));
  }

  private renderizarGraficosTab(tab: string): void {
    const res = this.resultado();
    if (!res) return;

    if (tab === 'pronostico') this.graficoRegresion(res.pronostico);
    else if (tab === 'simulacion') {
      this.graficoHistograma('histogramaA', res.simulacion.histograma_a, 'Escenario A — Sin Stock de Seguridad', 'rgba(59,130,246,0.75)', 'rgb(59,130,246)');
      this.graficoHistograma('histogramaB', res.simulacion.histograma_b, 'Escenario B — Con Stock de Seguridad', 'rgba(16,185,129,0.75)', 'rgb(16,185,129)');
      this.graficoCDF('graficoCDF', res.simulacion.cdf_a, res.simulacion.cdf_b);
    }
  }

  private graficoRegresion(p: PronosticoResult): void {
    // Última etiqueta es el período pronosticado, pintado diferente
    const etiquetas = [...p.periodos.map(String), `P${p.periodo_pronosticado} ★`];
    const ajustadosConPronostico = [...p.valores_ajustados, p.demanda_pronosticada];
    const demandaConVacio: (number | null)[] = [...p.demanda_historica, null];

    const config: ChartConfiguration = {
      type: 'line',
      data: {
        labels: etiquetas,
        datasets: [
          {
            label: 'Demanda real',
            data: demandaConVacio,
            borderColor: 'rgb(59,130,246)',
            backgroundColor: 'rgba(59,130,246,0.12)',
            pointRadius: 6,
            pointHoverRadius: 8,
            tension: 0.1,
            spanGaps: false,
          },
          {
            label: `Línea de regresión (R²=${p.r_cuadrado.toFixed(3)})`,
            data: ajustadosConPronostico,
            borderColor: 'rgb(239,68,68)',
            borderDash: [6, 4],
            pointRadius: ajustadosConPronostico.map((_, i) => i === ajustadosConPronostico.length - 1 ? 8 : 0),
            pointBackgroundColor: 'rgb(239,68,68)',
            backgroundColor: 'transparent',
            tension: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toLocaleString('es-CR', { maximumFractionDigits: 0 })} uds`,
            },
          },
        },
        scales: {
          x: { title: { display: true, text: 'Período' } },
          y: { title: { display: true, text: 'Demanda (unidades)' } },
        },
      },
    };
    this.crearChart('canvasRegresion', config);
  }

  private graficoHistograma(canvasId: string, hist: HistogramaData, titulo: string, colorFill: string, colorBorde: string): void {
    // Identificar el bin más cercano al valor esperado para pintarlo de rojo
    let indexMedia = 0;
    let minDist = Infinity;
    hist.centros.forEach((c, i) => {
      const d = Math.abs(c - hist.valor_esperado);
      if (d < minDist) { minDist = d; indexMedia = i; }
    });

    const colores = hist.centros.map((_, i) => i === indexMedia ? 'rgba(239,68,68,0.9)' : colorFill);
    const coloresBorde = hist.centros.map((_, i) => i === indexMedia ? 'rgb(239,68,68)' : colorBorde);

    const etiquetas = hist.centros.map(c => {
      const k = Math.round(c / 1000);
      return `₡${k}k`;
    });

    const config: ChartConfiguration = {
      type: 'bar',
      data: {
        labels: etiquetas,
        datasets: [{
          label: titulo,
          data: hist.frecuencias,
          backgroundColor: colores,
          borderColor: coloresBorde,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: [titulo, `▼ Línea roja = Valor Esperado (${this.crc(hist.valor_esperado)})`],
            font: { size: 13 },
          },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.parsed.y} escenarios`,
              title: ctxs => `Utilidad ≈ ${this.crc(hist.centros[ctxs[0].dataIndex])}`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: 'Utilidad por período (CRC)' },
            ticks: { maxTicksLimit: 10 },
          },
          y: { title: { display: true, text: '# de escenarios' } },
        },
      },
    };
    this.crearChart(canvasId, config);
  }

  private graficoCDF(canvasId: string, cdfA: CDFData, cdfB: CDFData): void {
    const config: ChartConfiguration = {
      type: 'line',
      data: {
        datasets: [
          {
            label: 'Escenario A (EOQ)',
            data: cdfA.valores.map((v, i) => ({ x: v, y: cdfA.probabilidades[i] * 100 })),
            borderColor: 'rgb(59,130,246)',
            backgroundColor: 'transparent',
            pointRadius: 0,
            tension: 0.15,
          },
          {
            label: 'Escenario B (EOQ + SS)',
            data: cdfB.valores.map((v, i) => ({ x: v, y: cdfB.probabilidades[i] * 100 })),
            borderColor: 'rgb(16,185,129)',
            backgroundColor: 'transparent',
            pointRadius: 0,
            tension: 0.15,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { position: 'top' },
          title: {
            display: true,
            text: 'Distribución de Probabilidad Acumulada (CDF)',
            font: { size: 13 },
          },
          tooltip: {
            callbacks: {
              label: ctx => `P(Utilidad ≤ ${this.crc(ctx.parsed.x ?? 0)}) = ${(ctx.parsed.y ?? 0).toFixed(1)}%`,
            },
          },
        },
        scales: {
          x: {
            type: 'linear',
            title: { display: true, text: 'Utilidad (CRC)' },
          },
          y: {
            min: 0,
            max: 100,
            title: { display: true, text: 'Probabilidad acumulada (%)' },
          },
        },
      },
    };
    this.crearChart(canvasId, config);
  }

  private crearChart(canvasId: string, config: ChartConfiguration): void {
    const canvas = document.getElementById(canvasId) as HTMLCanvasElement | null;
    if (!canvas) return;

    // Destruir instancia previa si existe, para evitar el error "Canvas already in use"
    if (this.graficos.has(canvasId)) {
      this.graficos.get(canvasId)!.destroy();
    }
    this.graficos.set(canvasId, new Chart(canvas, config));
  }

  ngOnDestroy(): void {
    this.graficos.forEach(chart => chart.destroy());
  }
}
