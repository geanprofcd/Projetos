-- Rodar depois de criar funil, oportunidade e mover etapa pela UI.
-- Exibe apenas quantidades agregadas, sem dados pessoais.
SELECT
 (SELECT count(*) FROM public.sales_funnels) AS funis,
 (SELECT count(*) FROM public.funnel_stages) AS etapas,
 (SELECT count(*) FROM public.opportunities) AS oportunidades,
 (SELECT count(*) FROM public.opportunity_stage_history) AS movimentos_historico,
 (SELECT count(*) FROM public.opportunities o WHERE o.status='open' AND o.ticket_id IS NOT NULL) AS oportunidades_abertas_vinculadas,
 (SELECT count(*) FROM (SELECT ticket_id FROM public.opportunities
    WHERE status='open' AND archived_at IS NULL AND ticket_id IS NOT NULL
    GROUP BY ticket_id HAVING count(*) > 1) x) AS tickets_com_duplicidade;
