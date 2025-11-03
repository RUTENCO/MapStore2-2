# Flujo de Datos SAT - Correcciones Aplicadas

## 🔄 **Flujo de Datos Corregido**

### **Estructura de Directorios (Host)**
```
fwdcdigosparavisor/
└── data/
    ├── input/                    # Archivos de entrada compartidos
    │   ├── Region_andina_VivianaUrrea.*
    │   └── estaciones_SAT_revis_nombres.*
    └── output/                   # Salidas por servicio
        ├── lluvia/              # Salida de lluvia_processor
        ├── modelo/              # Salida de modelo_sat
        └── geotiff/            # Salida de geotiff_exporter
```

### **Mapeo de Volúmenes Docker**

#### **🌧️ Lluvia Processor**
```yaml
volumes:
  - ./data/input:/app/data/input:ro          # Lee shapefiles
  - ./data/output/lluvia:/app/data/output/lluvia:rw  # Escribe datos de lluvia
```

#### **🤖 Modelo SAT**
```yaml
volumes:
  - ./data/input:/app/data/input:ro                    # Lee shapefiles
  - ./data/output/lluvia:/app/data/output/lluvia:ro    # Lee datos de lluvia
  - ./data/output/modelo:/app/data/output/modelo:rw    # Escribe predicciones
```

#### **🗺️ GeoTIFF Exporter**
```yaml
volumes:
  - ./data/input:/app/data/input:ro                      # Lee shapefiles
  - ./data/output/modelo:/app/data/output/modelo:ro      # Lee predicciones
  - ./data/output/geotiff:/app/data/output/geotiff:rw    # Escribe GeoTIFF
```

## 📊 **Flujo de Procesamiento**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Lluvia         │    │  Modelo         │    │  GeoTIFF        │
│  Processor      │───▶│  SAT            │───▶│  Exporter       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
  lluvia_procesada        predicciones_sat     probabilidad_
  _latest.csv            _latest.csv/.gpkg    deslizamientos_
                                              latest.tif
```

## 🔧 **Rutas en Código Python**

### **Lluvia Processor (`main.py`)**
```python
self.input_path = Path('/app/data/input')           # Shapefiles
self.output_path = Path('/app/data/output/lluvia')  # Salida lluvia
```

### **Modelo SAT (`main.py`)**
```python
self.input_path = Path('/app/data/output/lluvia')   # Lee datos lluvia
self.output_path = Path('/app/data/output/modelo')  # Salida predicciones
self.data_path = Path('/app/data/input')            # Shapefiles
```

### **GeoTIFF Exporter (`main.py`)**
```python
self.input_path = Path('/app/data/output/modelo')   # Lee predicciones
self.output_path = Path('/app/data/output/geotiff') # Salida GeoTIFF
self.data_path = Path('/app/data/input')            # Shapefiles
```

## ✅ **Correcciones Aplicadas**

### 1. **Eliminación de Carpetas Vacías**
- ❌ Eliminé: `lluvia_processor/data/` (vacía)
- ❌ Eliminé: `modelo_sat/data/` (vacía)
- ❌ Eliminé: `geotiff_exporter/data/` (vacía)

### 2. **Corrección de Rutas en Código**
- ✅ **Lluvia Processor**: Rutas actualizadas para usar estructura compartida
- ✅ **Modelo SAT**: Lee de salida de lluvia, escribe en salida de modelo
- ✅ **GeoTIFF Exporter**: Lee de salida de modelo, escribe en salida de geotiff

### 3. **Corrección de Volúmenes Docker**
- ✅ **docker-compose.yml**: Mapeos de volúmenes corregidos
- ✅ **Separación clara**: Input compartido, outputs específicos por servicio

### 4. **Script de Inicialización**
- ✅ **inicializar_sat.bat**: Eliminado copiado innecesario de archivos
- ✅ **Simplificación**: Los archivos se montan como volúmenes compartidos

## 📋 **Verificación del Flujo**

### **Paso 1: Lluvia Processor**
```
INPUT:  /app/data/input/*.shp
OUTPUT: /app/data/output/lluvia/lluvia_procesada_latest.csv
```

### **Paso 2: Modelo SAT**
```
INPUT:  /app/data/output/lluvia/lluvia_procesada_latest.csv
        /app/data/input/*.shp
OUTPUT: /app/data/output/modelo/predicciones_sat_latest.csv
        /app/data/output/modelo/predicciones_sat_latest.gpkg
```

### **Paso 3: GeoTIFF Exporter**
```
INPUT:  /app/data/output/modelo/predicciones_sat_latest.gpkg
        /app/data/input/Region_andina_VivianaUrrea.shp
OUTPUT: /app/data/output/geotiff/probabilidad_deslizamientos_latest.tif
```

## 🎯 **Resultado Final**

✅ **Flujo de datos completamente funcional**  
✅ **Estructura limpia sin carpetas vacías**  
✅ **Mapeo de volúmenes optimizado**  
✅ **Código Python actualizado con rutas correctas**  
✅ **Scripts de inicialización simplificados**  

**¡El pipeline SAT ahora tiene un flujo de datos perfecto y optimizado!** 🚀
