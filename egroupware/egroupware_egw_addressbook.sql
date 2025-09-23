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
-- Table structure for table `egw_addressbook`
--

DROP TABLE IF EXISTS `egw_addressbook`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_addressbook` (
  `contact_id` int(11) NOT NULL AUTO_INCREMENT,
  `contact_tid` char(1) DEFAULT 'n',
  `contact_owner` bigint(20) NOT NULL DEFAULT '0',
  `contact_private` tinyint(4) DEFAULT '0',
  `cat_id` varchar(255) DEFAULT NULL,
  `n_family` varchar(64) DEFAULT NULL,
  `n_given` varchar(64) DEFAULT NULL,
  `n_middle` varchar(64) DEFAULT NULL,
  `n_prefix` varchar(64) DEFAULT NULL,
  `n_suffix` varchar(64) DEFAULT NULL,
  `n_fn` varchar(128) DEFAULT NULL,
  `n_fileas` varchar(255) DEFAULT NULL,
  `contact_bday` varchar(12) DEFAULT NULL,
  `org_name` varchar(128) DEFAULT NULL,
  `org_unit` varchar(64) DEFAULT NULL,
  `contact_title` varchar(64) DEFAULT NULL,
  `contact_role` varchar(64) DEFAULT NULL,
  `contact_assistent` varchar(64) DEFAULT NULL,
  `contact_room` varchar(64) DEFAULT NULL,
  `adr_one_street` varchar(64) DEFAULT NULL,
  `adr_one_street2` varchar(64) DEFAULT NULL,
  `adr_one_locality` varchar(64) DEFAULT NULL,
  `adr_one_region` varchar(64) DEFAULT NULL,
  `adr_one_postalcode` varchar(64) DEFAULT NULL,
  `adr_one_countryname` varchar(64) DEFAULT NULL,
  `contact_label` text,
  `adr_two_street` varchar(64) DEFAULT NULL,
  `adr_two_street2` varchar(64) DEFAULT NULL,
  `adr_two_locality` varchar(64) DEFAULT NULL,
  `adr_two_region` varchar(64) DEFAULT NULL,
  `adr_two_postalcode` varchar(64) DEFAULT NULL,
  `adr_two_countryname` varchar(64) DEFAULT NULL,
  `tel_work` varchar(40) DEFAULT NULL,
  `tel_cell` varchar(40) DEFAULT NULL,
  `tel_fax` varchar(40) DEFAULT NULL,
  `tel_assistent` varchar(40) DEFAULT NULL,
  `tel_car` varchar(40) DEFAULT NULL,
  `tel_pager` varchar(40) DEFAULT NULL,
  `tel_home` varchar(40) DEFAULT NULL,
  `tel_fax_home` varchar(40) DEFAULT NULL,
  `tel_cell_private` varchar(40) DEFAULT NULL,
  `tel_other` varchar(40) DEFAULT NULL,
  `tel_prefer` varchar(32) DEFAULT NULL,
  `contact_email` varchar(128) DEFAULT NULL,
  `contact_email_home` varchar(128) DEFAULT NULL,
  `contact_url` varchar(128) DEFAULT NULL,
  `contact_url_home` varchar(128) DEFAULT NULL,
  `contact_freebusy_uri` varchar(128) DEFAULT NULL,
  `contact_calendar_uri` varchar(128) DEFAULT NULL,
  `contact_note` text,
  `contact_tz` varchar(8) DEFAULT NULL,
  `contact_geo` varchar(32) DEFAULT NULL,
  `contact_pubkey` text,
  `contact_created` bigint(20) DEFAULT NULL,
  `contact_creator` int(11) NOT NULL DEFAULT '0',
  `contact_modified` bigint(20) NOT NULL DEFAULT '0',
  `contact_modifier` int(11) DEFAULT NULL,
  `contact_jpegphoto` longblob,
  `account_id` int(11) DEFAULT NULL,
  `contact_etag` int(11) DEFAULT '0',
  `contact_uid` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`contact_id`),
  UNIQUE KEY `egw_addressbook_account_id` (`account_id`),
  KEY `egw_addressbook_cat_id` (`cat_id`),
  KEY `egw_addressbook_contact_owner` (`contact_owner`),
  KEY `egw_addressbook_n_fileas` (`n_fileas`),
  KEY `egw_addressbook_n_family_n_given` (`n_family`,`n_given`),
  KEY `egw_addressbook_n_given_n_family` (`n_given`,`n_family`),
  KEY `egw_addressbook_org_name_n_family_n_given` (`org_name`,`n_family`,`n_given`),
  KEY `egw_addressbook_contact_uid` (`contact_uid`)
) ENGINE=MyISAM AUTO_INCREMENT=19587 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:41:27
