"""
Pipeline de Entrenamiento ML (Fase 3)
=====================================
Orquesta la extracción de datos, el entrenamiento de Dixon-Coles y el Ensemble XGBoost,
y la serialización de los modelos resultantes.
"""

import os
import sys

# Agregar la raíz del backend al path para poder importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.data_loader import DataLoader
from models.dixon_coles import ModeloDixonColes
from models.xgboost_result import ModeloEnsemble1X2

def main():
    print("============================================================")
    print("  PREDICTOR FÚTBOL — Pipeline de Entrenamiento (Fase 3)")
    print("============================================================")
    
    loader = DataLoader()

    # ---------------------------------------------------------
    # 1. Entrenamiento Dixon-Coles (Modelo Matemático de Goles)
    # ---------------------------------------------------------
    print("\n[1/3] Extrayendo datos históricos para Dixon-Coles...")
    dc_data = loader.load_dixon_coles_data()
    
    if not dc_data:
        print("❌ Error: No hay suficientes partidos finalizados en la BD para Dixon-Coles.")
        return

    print(f"  ✓ {len(dc_data)} partidos recuperados.")
    
    print("\n[2/3] Entrenando modelo Dixon-Coles (L-BFGS-B Optimization)...")
    dc_model = ModeloDixonColes()
    # Ajustamos max_iter a 300 para no demorar eternamente en la demo
    dc_metrics = dc_model.entrenar(dc_data, max_iter=300, verbose=True)
    
    if dc_metrics["convergido"]:
        print(f"  ✓ Dixon-Coles entrenado exitosamente!")
        print(f"    - Equipos aprendidos: {dc_metrics['n_equipos']}")
        print(f"    - Ventaja localía (Gamma): {dc_metrics['gamma']}")
        print(f"    - Factor correlación baja punt. (Rho): {dc_metrics['rho']}")
    else:
        print("  ⚠ Advertencia: El optimizador no convergió completamente, pero los pesos fueron ajustados.")

    # ---------------------------------------------------------
    # 2. Entrenamiento XGBoost Ensemble (Machine Learning 1X2)
    # ---------------------------------------------------------
    print("\n[3/3] Entrenando Ensemble XGBoost + Random Forest + Regresión...")
    X, y, feature_names = loader.load_xgboost_data()
    
    if len(X) < 10:
        print("❌ Error: No hay suficientes features completadas para entrenar XGBoost.")
        return
        
    print(f"  ✓ {len(X)} muestras recuperadas con {len(feature_names)} features (e ej. ELO_diff, xG_diff).")
    
    xgb_model = ModeloEnsemble1X2()
    xgb_metrics = xgb_model.entrenar(X, y, feature_names=feature_names, verbose=True)
    
    print(f"\n  ✓ Modelos Base: {', '.join(xgb_metrics['modelos_base'])}")
    print(f"  ✓ Meta Learner: {xgb_metrics['meta_learner']}")
    print(f"  ✓ Accuracy final (Capa Stacking): {xgb_metrics['accuracy_train']*100:.1f}%")
    
    print("\n[i] Features más importantes (XGBoost):")
    for feat in xgb_model.importancia_features(top_n=5):
        print(f"    - {feat['feature']}: {feat['importancia']:.4f}")

    # ---------------------------------------------------------
    # 3. Guardar Modelos
    # ---------------------------------------------------------
    print("\n[✓] Guardando modelos serializados en /artifacts...")
    # Serializar xgb_model ya está implementado en la clase
    xgb_model.guardar("ensemble_1x2_v1")
    
    # Serializar dixon_coles
    import joblib
    artifact_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts", "models")
    os.makedirs(artifact_dir, exist_ok=True)
    joblib.dump(dc_model, os.path.join(artifact_dir, "dixon_coles_v1.joblib"))
    
    print("\n🎉 Pipeline completado exitosamente. La API ya puede servir predicciones reales.")

if __name__ == "__main__":
    main()
