# Relatório de Vendas - Yooga

Este projeto é um dashboard interativo para análise de vendas e taxas de serviço do delivery Yooga, desenvolvido em Python utilizando Streamlit.

## Funcionalidades
- Consulta de dados de vendas e pagamentos diretamente das APIs Yooga
- Visualização de métricas financeiras: valor bruto, TPV, valor líquido, valor a repassar, total de pedidos e taxa de serviço
- Busca otimizada e robusta, com tratamento de erros e tentativas automáticas
- Sistema de cache para acelerar consultas repetidas
- Interface intuitiva com entrada de token e datas via sidebar

## Estrutura do Projeto
- `main.py`: Ponto de entrada da aplicação Streamlit
- `services.py`: Funções para buscar dados nas APIs, calcular totais e validar token
- `ui.py`: Componentes visuais para exibir métricas e converter datas
- `config.py`: Configurações de URLs das APIs e timezone
- Arquivos de backup e dados (`bkp/`, `bkp_inicio/`, arquivos .json)

## Como executar localmente
1. Instale as dependências:
   ```bash
   pip install streamlit aiohttp tenacity pyjwt pytz
   ```
2. Execute o dashboard:
   ```bash
   streamlit run main.py
   ```
3. Insira o Token JWT e selecione o período desejado na barra lateral.

## Deploy
Para publicar online, recomenda-se o uso do [Streamlit Cloud](https://streamlit.io/cloud) ou serviços como Heroku, Azure Web Apps, etc. O Vercel não suporta aplicações Streamlit diretamente.

## Observações
- O sistema faz buscas concorrentes nas APIs, respeitando limites para evitar bloqueios.
- Em caso de rate limit ou falha, o sistema tenta novamente automaticamente.
- O cache armazena resultados de consultas para acelerar buscas repetidas.

## Licença
Projeto privado para uso interno Yooga.
