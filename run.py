import socket
import sys
import os
import uvicorn

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    # Garante encoding UTF-8 no console do Windows
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    local_ip = get_local_ip()
    port = 8000

    print("=" * 66)
    print("  PEDIDOS GRANODOC - SISTEMA DE GESTAO DE SUPRIMENTOS")
    print("=" * 66)
    print(f"  [Computador Local]:          http://localhost:{port}")
    print(f"  [Celulares / Tablets Wi-Fi]: http://{local_ip}:{port}")
    print("-" * 66)
    print("  PINs Padrao de Acesso:")
    print("   - Pizzaiolo:     1001 (Pizzas e Massas)")
    print("   - Cozinha:       1002 (Cozinha Quente e Geral)")
    print("   - Barman:        1003 (Bebidas e Coquetelaria)")
    print("   - Salao:         1004 (Salao, Vinhos e Atendimento)")
    print("   - Administracao: 9999 (Acesso Master & Compras Consolidadas)")
    print("=" * 66)
    print("Iniciando servidor Uvicorn...\n")

    # Garante que o diretório atual está no path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
