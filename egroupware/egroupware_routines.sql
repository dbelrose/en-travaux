-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: dbpnf.srv.gov.pf    Database: egroupware
-- ------------------------------------------------------
-- Server version	5.5.43-0+deb7u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Temporary view structure for view `v_mdx`
--

DROP TABLE IF EXISTS `v_mdx`;
/*!50001 DROP VIEW IF EXISTS `v_mdx`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_mdx` AS SELECT 
 1 AS `annee`,
 1 AS `m`,
 1 AS `mois`,
 1 AS `el2`,
 1 AS `v.info_extra_value*1`,
 1 AS `groupe`,
 1 AS `valeur`,
 1 AS `etat_description`,
 1 AS `info_extra_name_description`,
 1 AS `info_type_description`,
 1 AS `etat_sous_titre`*/;
SET character_set_client = @saved_cs_client;

--
-- Final view structure for view `v_mdx`
--

/*!50001 DROP VIEW IF EXISTS `v_mdx`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`egroupware`@`%` SQL SECURITY DEFINER */
/*!50001 VIEW `v_mdx` AS select year(from_unixtime(`i`.`info_startdate`)) AS `annee`,((year(from_unixtime(`i`.`info_startdate`)) * 100) + month(from_unixtime(`i`.`info_startdate`))) AS `m`,concat(elt(month(from_unixtime(`i`.`info_startdate`)),'Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'),' ',year(from_unixtime(`i`.`info_startdate`))) AS `mois`,`ab`.`n_fn` AS `el2`,(`v`.`info_extra_value` * 1) AS `v.info_extra_value*1`,if(locate(':',`v`.`info_extra_value_description`),substring_index(`v`.`info_extra_value_description`,':',1),'') AS `groupe`,substring_index(`v`.`info_extra_value_description`,':',-(1)) AS `valeur`,`e`.`etat_description` AS `etat_description`,`n`.`info_extra_name_description` AS `info_extra_name_description`,`t`.`info_type_description` AS `info_type_description`,`e`.`etat_sous_titre` AS `etat_sous_titre` from (((((((`egw_accounts` `a` join `egw_addressbook` `ab`) join `egw_infolog` `i`) join `egw_infolog_extra` `ie`) join `sibdi_info_extra_value` `v`) join `sibdi_info_extra_name` `n`) join `sibdi_info_type` `t`) join `sibdi_etats` `e`) where ((`a`.`account_primary_group` = -(128)) and (`a`.`account_id` = `ab`.`account_id`) and (`e`.`info_type` = `t`.`info_type`) and (`e`.`info_extra_name` = `n`.`info_extra_name`) and (`v`.`info_type` = `t`.`info_type`) and (`i`.`info_type` = `v`.`info_type`) and (`ie`.`info_extra_name` = `v`.`info_extra_name`) and (`i`.`info_type` = `t`.`info_type`) and (`ie`.`info_extra_name` = `n`.`info_extra_name`) and (`i`.`info_owner` = `a`.`account_id`) and (`i`.`info_id` = `ie`.`info_id`) and (`t`.`info_type` = `n`.`info_type`) and (find_in_set(`v`.`info_extra_value`,`ie`.`info_extra_value`) > 0) and (year(now()) = year(from_unixtime(`i`.`info_startdate`)))) order by ((year(from_unixtime(`i`.`info_startdate`)) * 100) + month(from_unixtime(`i`.`info_startdate`))),substring_index(`v`.`info_extra_value_description`,':',-(1)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-07  7:59:54
