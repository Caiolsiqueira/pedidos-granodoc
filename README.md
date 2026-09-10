# 🍕 Pedidos Granodoc - Sistema de Gestão de Suprimentos

Sistema web completo, profissional e responsivo para gestão interna de compras e requisições de insumos de restaurante e pizzaria.

---

## 🚀 Como Executar

### Opção 1: Via script facilitador na raiz
No terminal na pasta principal:
```powershell
python run_granodoc.py
```

### Opção 2: Diretamente dentro do módulo
```powershell
cd pedidos_granodoc
python run.py
```
O servidor iniciará automaticamente em `http://localhost:8000` e exibirá o IP da rede local para você testar no celular ou tablet na bancada de trabalho!

---

## 🔑 Perfis de Acesso e PINs de 4 Dígitos

| Perfil / Setor | PIN Padrão | Escopo de Acesso |
|---|---|---|
| **🍕 Pizzaiolo** | `1001` | Insumos de pizzas, massas, molhos e queijos especiais |
| **🍳 Cozinha** | `1002` | Carnes, hortifrúti, laticínios, risotos e cozinha quente |
| **🍸 Barman** | `1003` | Bebidas, destilados, frutas frescas, xaropes e refrigerantes |
| **🍷 Salão** | `1004` | Salão, atendimento, vinhos, espumantes e acessórios |
| **🛡️ Administração** | `9999` | **Acesso Master**: todas as praças, consolidação unificada e cotação |

> **Regra RBAC:** Usuários operacionais nunca enxergam dados de outros setores. A Administração tem passe livre em tudo e conta com o **Modo Auditoria**.

---

## 🌟 Principais Funcionalidades

### 📱 1. Telas Operacionais (Mobile-First Touch)
- **Teclado Numérico Virtual:** Inserção de PIN de 4 dígitos com animação de shake e submissão automática.
- **Catálogo de Insumos com Toque Fácil:** Botões amplos de incremento (`+` e `−`), atalhos rápidos (`+1`, `+5`) e busca instantânea.
- **Itens Extras / Fora de Catálogo:** Formulário ágil para solicitar insumos não cadastrados com descrição, quantidade e unidade.
- **Carrinho / Resumo em Tempo Real:**
  - *No Mobile:* Barra inferior flutuante fixa e *bottom sheet* retrátil.
  - *No Desktop:* Painel lateral *sticky* com campo de observações para compras.
- **Histórico Recente (7 dias):** Visualização retrátil de todos os pedidos enviados pelo setor com status colorido em tempo real.

### 📊 2. Painel Master da Administração
- **Aba 1: Pedidos por Data (Visão Diária):** Filtros por data, praça e status com alteração de status em um clique (`Pendente` $\rightarrow$ `Aprovado` $\rightarrow$ `Comprado`).
- **Aba 2: Lista Consolidada de Compras (Ordem Unificada):** Agrupamento automático em SQL somando volumes de múltiplos setores para cotação com fornecedores.
  - **Copiar para WhatsApp:** Gera mensagem formatada com negritos, marcadores e emojis para envio instantâneo a fornecedores.
  - **Exportar para PDF:** Gera documento PDF profissional via ReportLab com cabeçalho, tabelas e linhas de assinatura.
- **Aba 3: Modo Auditoria:** Permite à administração inspecionar a interface exatamente como qualquer operador enxerga.
- **Aba 4: Gestão do Catálogo:** Cadastro de novos insumos e ativação/desativação de produtos.
- **Light Mode & Dark Mode:** Alternância nativa com persistência em `localStorage`.

---

## 🧪 Testes Automatizados

Para rodar os testes unitários e de integração:
```powershell
python pedidos_granodoc\test_granodoc.py
python pedidos_granodoc\test_server_integration.py
```
Ambas as suítes cobrem 100% dos fluxos de dados, autenticação, esteira de status e consolidação SQL.
