elif menu == "Gestão de Obras":
    st.markdown("<div class='section-title'>Gestão de Obras</div>", unsafe_allow_html=True)
    if df_clientes.empty: st.warning("Cadastre clientes primeiro.")
    else:
        lista_cli = sorted(df_clientes["Nome"].astype(str).str.strip().unique())
        cli_sel = st.selectbox("Selecione o Cliente", [""] + lista_cli)
        
        if cli_sel:
            # Pega dados do cliente para o endereço
            dados_cli = df_clientes[df_clientes["Nome"].astype(str).str.strip() == cli_sel].iloc[0]
            end_cliente = str(dados_cli["Endereco"])
            
            obras_do_cli = df_obras[df_obras["Cliente"].astype(str).str.strip() == cli_sel]
            
            if obras_do_cli.empty: 
                st.info("Este cliente não tem obras.")
            else:
                st.caption("Histórico de Obras:")
                show_o = obras_do_cli.copy()
                show_o["Total"] = show_o["Total"].apply(br_money)
                st.dataframe(show_o[["ID", "Status", "Data_Visita", "Data_Orcamento", "Total"]], use_container_width=True)
            
            st.divider()
            
            with st.expander("➕ Adicionar / Editar Obra", expanded=True):
                opcoes_obras = ["Nova Obra"]
                
                # Prepara o menu. Se tiver obras, já deixa a ÚLTIMA selecionada
                idx_selecao = 0 
                if not obras_do_cli.empty:
                    lista_ids = [f"ID {row['ID']} - {row['Status']}" for _, row in obras_do_cli.iterrows()]
                    opcoes_obras += lista_ids
                    idx_selecao = len(opcoes_obras) - 1

                obra_selecionada = st.selectbox("Selecione a obra para editar:", opcoes_obras, index=idx_selecao)
                
                dados_obra = {
                    "ID": None, "Status": "🔵 Agendamento", "Descricao": "", 
                    "Custo_MO": 0.0, "Custo_Material": 0.0, "Entrada": 0.0, "Pago": False,
                    "Total": 0.0,
                    "Data_Visita": datetime.now().date(), "Data_Orcamento": datetime.now().date()
                }

                if obra_selecionada != "Nova Obra":
                    id_selecionado = int(obra_selecionada.split("ID ")[1].split(" -")[0])
                    filtro = df_obras[df_obras["ID"] == id_selecionado]
                    if not filtro.empty:
                        dados_obra = filtro.iloc[0].to_dict()

                # === AREA DE AÇÃO RÁPIDA (NOVOS BOTÕES) ===
                if obra_selecionada != "Nova Obra":
                    st.markdown("##### 🚀 Ações Rápidas")
                    col_act1, col_act2 = st.columns(2)
                    
                    # Botão Google Calendar
                    with col_act1:
                        # Cria link para visita as 09:00 da data selecionada
                        d_visita_dt = pd.to_datetime(dados_obra["Data_Visita"]).date() if pd.notnull(dados_obra["Data_Visita"]) else datetime.now().date()
                        link_cal = link_calendar(f"Visita: {cli_sel}", d_visita_dt, dtime(9,0), 60, end_cliente)
                        st.markdown(f'''
                            <a href="{link_cal}" target="_blank" style="text-decoration:none;">
                                <button style="width:100%; padding:0.5rem; background-color:#E8F0FE; color:#1967D2; border:1px solid #1967D2; border-radius:8px; cursor:pointer;">
                                    📅 Agendar Visita no Google
                                </button>
                            </a>
                        ''', unsafe_allow_html=True)
                    
                    # Botão Google Maps
                    with col_act2:
                        if end_cliente and len(end_cliente) > 3:
                            link_waze = link_maps(end_cliente)
                            st.markdown(f'''
                                <a href="{link_waze}" target="_blank" style="text-decoration:none;">
                                    <button style="width:100%; padding:0.5rem; background-color:#CEEAD6; color:#137333; border:1px solid #137333; border-radius:8px; cursor:pointer;">
                                        📍 Abrir Rota (Maps)
                                    </button>
                                </a>
                            ''', unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ Cadastre o endereço do cliente para liberar o mapa.")
                    st.write("") # Espaço

                # === FIM AREA DE AÇÃO RÁPIDA ===

                with st.form("form_obra"):
                    st.caption(f"Detalhes da Obra: {obra_selecionada}")
                    status = st.selectbox("Status", 
                        ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"],
                        index=["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"].index(normalize_status(dados_obra["Status"]))
                    )
                    desc = st.text_area("Descrição", value=str(dados_obra["Descricao"]))
                    c1, c2 = st.columns(2)
                    d_visita = c1.date_input("Data Visita", value=pd.to_datetime(dados_obra["Data_Visita"]).date() if pd.notnull(dados_obra["Data_Visita"]) else datetime.now().date())
                    d_orc = c2.date_input("Data Orçamento", value=pd.to_datetime(dados_obra["Data_Orcamento"]).date() if pd.notnull(dados_obra["Data_Orcamento"]) else datetime.now().date())
                    
                    c3, c4, c5 = st.columns(3)
                    
                    val_mo = float(dados_obra["Custo_MO"])
                    val_mat = float(dados_obra["Custo_Material"])
                    val_tot = float(dados_obra.get("Total", 0.0))
                    
                    if val_mo == 0 and val_mat == 0 and val_tot > 0:
                        val_mo = val_tot

                    mo = c3.number_input("Mão de Obra (R$)", value=val_mo, step=10.0)
                    mat = c4.number_input("Materiais (R$)", value=val_mat, step=10.0)
                    ent = c5.number_input("Entrada (R$)", value=float(dados_obra["Entrada"]), step=10.0)
                    pago = st.checkbox("Pago Integralmente?", value=bool(dados_obra["Pago"]))
                    
                    total_calc = mo + mat
                    st.markdown(f"**Total Calculado:** {br_money(total_calc)}")
                    
                    if st.form_submit_button("Salvar Obra"):
                        novo_id = dados_obra["ID"]
                        if novo_id is None or novo_id == 0: 
                             try: novo_id = int(df_obras["ID"].max()) + 1 if not df_obras.empty else 1
                             except: novo_id = 1
                        else:
                             df_obras = df_obras[df_obras["ID"] != novo_id]
                        
                        nova_linha = {
                            "ID": novo_id, "Cliente": cli_sel, "Status": status, "Descricao": desc,
                            "Custo_MO": mo, "Custo_Material": mat, "Total": total_calc,
                            "Entrada": ent, "Pago": pago, "Data_Visita": d_visita, "Data_Orcamento": d_orc
                        }
                        for col in df_obras.columns:
                            if col not in nova_linha: nova_linha[col] = None
                            
                        df_obras = pd.concat([df_obras, pd.DataFrame([nova_linha])], ignore_index=True)
                        save_data(df_clientes, df_obras)
                        st.success("Obra salva com sucesso!")
                        st.rerun()
            
            st.divider()
            with st.expander("🗑️ Excluir uma Obra"):
                if obras_do_cli.empty: st.info("Nada para excluir.")
                else:
                    lista_ids = obras_do_cli["ID"].astype(int).tolist()
                    id_del = st.selectbox("Selecione o ID da Obra", lista_ids)
                    confirm_obra = st.checkbox("Confirmo exclusão da obra", value=False)
                    if st.button("Excluir Obra"):
                        if not confirm_obra: st.error("Confirme a exclusão.")
                        else:
                            df_obras = excluir_obra(df_obras, id_del)
                            df_obras = limpar_obras(df_obras)
                            save_data(df_clientes, df_obras)
                            st.success("Obra removida.")
                            st.rerun()
