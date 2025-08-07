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
-- Table structure for table `phpgw_fud_msg`
--

DROP TABLE IF EXISTS `phpgw_fud_msg`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_fud_msg` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `thread_id` int(11) NOT NULL DEFAULT '0',
  `poster_id` int(11) NOT NULL DEFAULT '0',
  `reply_to` int(11) NOT NULL DEFAULT '0',
  `ip_addr` varchar(15) NOT NULL DEFAULT '0.0.0.0',
  `host_name` varchar(255) DEFAULT NULL,
  `post_stamp` bigint(20) NOT NULL DEFAULT '0',
  `update_stamp` bigint(20) NOT NULL DEFAULT '0',
  `updated_by` int(11) NOT NULL DEFAULT '0',
  `icon` varchar(100) DEFAULT NULL,
  `subject` varchar(100) DEFAULT NULL,
  `attach_cnt` int(11) NOT NULL DEFAULT '0',
  `poll_id` int(11) NOT NULL DEFAULT '0',
  `foff` bigint(20) NOT NULL DEFAULT '0',
  `length` int(11) NOT NULL DEFAULT '0',
  `file_id` int(11) NOT NULL DEFAULT '1',
  `offset_preview` bigint(20) NOT NULL DEFAULT '0',
  `length_preview` int(11) NOT NULL DEFAULT '0',
  `file_id_preview` int(11) NOT NULL DEFAULT '0',
  `attach_cache` text,
  `poll_cache` text,
  `mlist_msg_id` varchar(100) DEFAULT NULL,
  `msg_opt` int(11) NOT NULL DEFAULT '1',
  `apr` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`,`apr`),
  KEY `poster_id` (`poster_id`,`apr`),
  KEY `apr` (`apr`),
  KEY `post_stamp` (`post_stamp`),
  KEY `attach_cnt` (`attach_cnt`),
  KEY `poll_id` (`poll_id`),
  KEY `ip_addr` (`ip_addr`,`post_stamp`),
  KEY `subject` (`subject`),
  KEY `mlist_msg_id` (`mlist_msg_id`)
) ENGINE=MyISAM AUTO_INCREMENT=11 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-07  7:59:46
