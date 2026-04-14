"""
CLI entry point for the certificate generator.
Handles argument parsing and invokes the main generation logic.
"""

import argparse
import logging
import sys
from pathlib import Path

from generator import generate_certificates
from utils import setup_logging
import config


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate bulk certificates from a Canva-designed template in Google Slides',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --csv participants.csv --template 1abc2def3ghi --output ./certificates
  python main.py --csv data.csv --template 1abc2def3ghi --cleanup --verbose
  
For help and setup instructions, see README.md
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--csv',
        required=True,
        help='Path to CSV file with certificate data (Name, Email, etc.)'
    )
    
    parser.add_argument(
        '--template',
        required=True,
        help='Google Slides template ID (from presentation URL or Share link)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output',
        default=config.DEFAULT_OUTPUT_FOLDER,
        help=f'Output folder for PDF certificates (default: {config.DEFAULT_OUTPUT_FOLDER})'
    )
    
    parser.add_argument(
        '--creds',
        default=config.DEFAULT_CREDENTIALS_PATH,
        help=f'Path to service account credentials.json (default: {config.DEFAULT_CREDENTIALS_PATH})'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Delete temporary slides from Google Drive after success'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging to console'
    )
    
    parser.add_argument(
        '--clear-checkpoint',
        action='store_true',
        help='Clear resume checkpoint and regenerate all certificates'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.output, verbose=args.verbose)
    
    logging.info("=" * 70)
    logging.info("Certificate Generator Starting")
    logging.info("=" * 70)
    logging.info(f"CSV: {args.csv}")
    logging.info(f"Template ID: {args.template}")
    logging.info(f"Output: {args.output}")
    logging.info(f"Credentials: {args.creds}")
    logging.info(f"Cleanup temp slides: {args.cleanup}")
    
    # Validate inputs
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logging.error(f"CSV file not found: {csv_path}")
        print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
        return 1
    
    creds_path = Path(args.creds)
    if not creds_path.exists():
        logging.error(f"Credentials file not found: {creds_path}")
        print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
        print(f"\nSetup instructions: See SETUP_GUIDE.md", file=sys.stderr)
        return 1
    
    # Clear checkpoint if requested
    if args.clear_checkpoint:
        from utils import CheckpointManager
        checkpoint = CheckpointManager(args.output)
        checkpoint.clear()
        logging.info("Checkpoint cleared. All certificates will be regenerated.")
    
    try:
        # Run certificate generation
        summary = generate_certificates(
            csv_path=str(csv_path),
            template_id=args.template,
            output_folder=args.output,
            credentials_path=str(creds_path),
            cleanup=args.cleanup
        )
        
        # Print summary
        print("\n" + "=" * 70)
        print("CERTIFICATE GENERATION SUMMARY")
        print("=" * 70)
        print(f"Total rows:     {summary['total']}")
        print(f"Success:        {summary['success']}")
        print(f"Failed:         {summary['failed']}")
        print(f"Skipped:        {summary['skipped']}")
        
        if summary['errors']:
            print(f"\nErrors ({len(summary['errors'])} total):")
            for error in summary['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(summary['errors']) > 5:
                print(f"  ... and {len(summary['errors']) - 5} more")
        
        print(f"\nPDFs saved to: {args.output}")
        print(f"Log file: {Path(args.output) / 'certificate_generator.log'}")
        print("=" * 70)
        
        # Return exit code based on success
        if summary['failed'] == 0 and summary['success'] > 0:
            logging.info("Certificate generation completed successfully!")
            return 0
        elif summary['success'] > 0:
            logging.warning(f"Generation completed with {summary['failed']} failures")
            return 1
        else:
            logging.error("No certificates were generated")
            return 2
    
    except KeyboardInterrupt:
        logging.warning("Certificate generation interrupted by user")
        print("\nInterrupted. You can resume later with the same command.", file=sys.stderr)
        return 130
    
    except Exception as e:
        logging.exception("Fatal error during certificate generation")
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
