import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ParametrosAnalisis, ResultadoCompleto } from '../models/dss.models';

/** Servicio HTTP que conecta Angular con el backend FastAPI. */
@Injectable({ providedIn: 'root' })
export class DssService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:8000/api';

  /** Ejecuta el pipeline completo: pronóstico → inventario → Monte Carlo → reporte. */
  analizar(params: ParametrosAnalisis): Observable<ResultadoCompleto> {
    return this.http.post<ResultadoCompleto>(`${this.apiUrl}/analizar`, params);
  }

  /** Obtiene parámetros de ejemplo para una PyME importadora de repuestos. */
  obtenerDatosEjemplo(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${this.apiUrl}/datos-ejemplo`);
  }
}
