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
-- Table structure for table `phpgw_fud_pmsg`
--

DROP TABLE IF EXISTS `phpgw_fud_pmsg`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_fud_pmsg` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `to_list` text,
  `ouser_id` int(11) NOT NULL DEFAULT '0',
  `duser_id` int(11) NOT NULL DEFAULT '0',
  `pdest` int(11) NOT NULL DEFAULT '0',
  `ip_addr` varchar(15) NOT NULL DEFAULT '0.0.0.0',
  `host_name` varchar(255) DEFAULT NULL,
  `post_stamp` bigint(20) NOT NULL DEFAULT '0',
  `read_stamp` bigint(20) NOT NULL DEFAULT '0',
  `icon` varchar(100) DEFAULT NULL,
  `subject` varchar(100) DEFAULT NULL,
  `attach_cnt` int(11) NOT NULL DEFAULT '0',
  `foff` bigint(20) NOT NULL DEFAULT '0',
  `length` int(11) NOT NULL DEFAULT '0',
  `ref_msg_id` varchar(11) DEFAULT NULL,
  `fldr` int(11) NOT NULL DEFAULT '0',
  `pmsg_opt` int(11) NOT NULL DEFAULT '49',
  PRIMARY KEY (`id`),
  KEY `duser_id` (`duser_id`,`fldr`,`read_stamp`),
  KEY `duser_id_2` (`duser_id`,`fldr`,`id`)
) ENGINE=MyISAM AUTO_INCREMENT=17 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-10-22 10:59:15
