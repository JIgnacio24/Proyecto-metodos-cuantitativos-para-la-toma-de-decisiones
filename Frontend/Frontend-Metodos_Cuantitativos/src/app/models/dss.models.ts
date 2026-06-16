/** Modelos de datos del DSS — tipos TypeScript para los contratos con la API */

export interface ParametrosAnalisis {
  demanda_historica: number[];
  costo_unitario: number;
  precio_venta: number;
  costo_por_pedido: number;
  costo_mantener: number;
  costo_ruptura: number;
  lead_time: number;
  nivel_servicio: number;
  n_iteraciones: number;
  factor_incertidumbre: number;
}

export interface PronosticoResult {
  periodos: number[];
  demanda_historica: number[];
  valores_ajustados: number[];
  demanda_pronosticada: number;
  error_estandar: number;
  r_cuadrado: number;
  pendiente: number;
  intercepto: number;
  n_periodos: number;
  periodo_pronosticado: number;
}

export interface InventarioCostos {
  costo_ordenar: number;
  costo_mantener_total: number;
  costo_compra: number;
  costo_total: number;
  num_pedidos: number;
}

export interface InventarioResult {
  eoq: number;
  stock_seguridad: number;
  punto_reorden: number;
  inventario_promedio: number;
  nivel_servicio_usado: number;
  lead_time: number;
  costos: InventarioCostos;
}

export interface EstadisticasEscenario {
  media: number;
  desviacion_std: number;
  ic_95_inferior: number;
  ic_95_superior: number;
  var_95: number;
  prob_exito: number;
  prob_ruptura: number;
  utilidad_minima: number;
  utilidad_maxima: number;
  mediana: number;
  percentil_25: number;
  percentil_75: number;
}

export interface HistogramaData {
  centros: number[];
  frecuencias: number[];
  valor_esperado: number;
}

export interface CDFData {
  valores: number[];
  probabilidades: number[];
}

export interface SimulacionResult {
  Q_a: number;
  Q_b: number;
  sigma_usada: number;
  n_iteraciones: number;
  escenario_a: EstadisticasEscenario;
  escenario_b: EstadisticasEscenario;
  histograma_a: HistogramaData;
  histograma_b: HistogramaData;
  cdf_a: CDFData;
  cdf_b: CDFData;
}

export interface FilaComparacion {
  metrica: string;
  escenario_a: number;
  escenario_b: number;
  mejor: string;
  nota: string;
}

export interface ComparacionResult {
  tabla: FilaComparacion[];
  recomendacion: string;
}

export interface ResultadoCompleto {
  pronostico: PronosticoResult;
  inventario: InventarioResult;
  simulacion: SimulacionResult;
  comparacion: ComparacionResult;
}
