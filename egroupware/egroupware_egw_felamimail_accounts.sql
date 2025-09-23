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
-- Table structure for table `egw_felamimail_accounts`
--

DROP TABLE IF EXISTS `egw_felamimail_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_felamimail_accounts` (
  `fm_owner` int(11) NOT NULL DEFAULT '0',
  `fm_id` int(11) NOT NULL AUTO_INCREMENT,
  `fm_realname` varchar(128) DEFAULT NULL,
  `fm_organization` varchar(128) DEFAULT NULL,
  `fm_emailaddress` varchar(128) NOT NULL DEFAULT '',
  `fm_ic_hostname` varchar(128) DEFAULT NULL,
  `fm_ic_port` int(11) DEFAULT NULL,
  `fm_ic_username` varchar(128) DEFAULT NULL,
  `fm_ic_password` varchar(128) DEFAULT NULL,
  `fm_ic_encryption` int(11) DEFAULT NULL,
  `fm_og_hostname` varchar(128) DEFAULT NULL,
  `fm_og_port` int(11) DEFAULT NULL,
  `fm_og_smtpauth` tinyint(4) DEFAULT NULL,
  `fm_og_username` varchar(128) DEFAULT NULL,
  `fm_og_password` varchar(128) DEFAULT NULL,
  `fm_active` tinyint(4) NOT NULL DEFAULT '0',
  `fm_ic_validatecertificate` tinyint(4) DEFAULT NULL,
  `fm_ic_enable_sieve` tinyint(4) DEFAULT NULL,
  `fm_ic_sieve_server` varchar(128) DEFAULT NULL,
  `fm_ic_sieve_port` int(11) DEFAULT NULL,
  `fm_signatureid` int(11) DEFAULT NULL,
  `fm_ic_folderstoshowinhome` text,
  `fm_ic_sentfolder` varchar(128) DEFAULT NULL,
  `fm_ic_trashfolder` varchar(128) DEFAULT NULL,
  `fm_ic_draftfolder` varchar(128) DEFAULT NULL,
  `fm_ic_templatefolder` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`fm_id`),
  KEY `fm_accounts_owner` (`fm_owner`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:41:08
